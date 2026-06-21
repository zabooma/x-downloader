import os
import re
import json
from datetime import date, datetime
from io import BytesIO

from nicegui import ui, run
from twarc import Twarc2
from requests.exceptions import HTTPError
import pandas as pd


# ---- Business logic ----

def _get_client(token: str) -> Twarc2:
    return Twarc2(bearer_token=token)


def _lookup_user(client: Twarc2, username: str) -> dict | None:
    # Use client.get() directly to avoid twarc2's _prepare_params injecting
    # tweet_fields (incl. context_annotations) which 400s on the free tier.
    try:
        resp = client.get(
            'https://api.twitter.com/2/users/by',
            params={
                'usernames': username,
                'user.fields': 'name,username,description,public_metrics',
            },
        )
    except HTTPError as e:
        body = e.response.json()
        detail = body.get('detail') or body.get('title') or str(body)
        raise Exception(detail) from None
    users = resp.json().get('data', [])
    return users[0] if users else None


def _fetch_timeline(client: Twarc2, user_id: str, start: date, end: date, max_results: int, include_refs: bool = False):
    posts: list[dict] = []
    tweet_map: dict = {}
    user_map: dict = {}
    truncated = False
    expansions = 'in_reply_to_user_id'
    if include_refs:
        expansions = 'referenced_tweets.id,referenced_tweets.id.author_id,in_reply_to_user_id'
    try:
        for response in client.timeline(
            user_id,
            max_results=100,
            start_time=start.strftime('%Y-%m-%dT00:00:00Z'),
            end_time=end.strftime('%Y-%m-%dT23:59:59Z'),
            tweet_fields='id,text,created_at,public_metrics,referenced_tweets,in_reply_to_user_id,conversation_id',
            expansions=expansions,
            user_fields='username,name',
        ):
            includes = response.get('includes', {})
            for t in includes.get('tweets', []):
                tweet_map[t['id']] = t
            for u in includes.get('users', []):
                user_map[u['id']] = u
            for tweet in response.get('data', []):
                posts.append(tweet)
                if len(posts) >= max_results:
                    return posts, tweet_map, user_map, False
    except Exception:
        if not posts:
            raise  # failed on the first page — nothing to salvage, propagate
        truncated = True
    return posts, tweet_map, user_map, truncated


def _format_dt(ts: str) -> str:
    if not ts:
        return ''
    return datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone().strftime('%Y-%m-%d %H:%M')


_TOKEN_RE = re.compile(r'(@\w+)|(https?://[A-Za-z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+)')

def _segment(text: str) -> list[dict]:
    """Split text into plain/mention/url segments for the Vue slot renderer."""
    segments: list[dict] = []
    pos = 0
    for m in _TOKEN_RE.finditer(text):
        if m.start() > pos:
            segments.append({'t': 'text', 'v': text[pos:m.start()]})
        if m.group(1):
            segments.append({'t': 'mention', 'v': m.group(1)[1:]})  # strip leading @
        else:
            segments.append({'t': 'url', 'v': m.group(2)})
        pos = m.end()
    if pos < len(text):
        segments.append({'t': 'text', 'v': text[pos:]})
    return segments


def _post_type(tweet: dict, author_id: str) -> str:
    refs = tweet.get('referenced_tweets', [])
    if not refs:
        return 'Original'
    t = refs[0]['type']
    if t == 'retweeted':
        return 'Retweet'
    if t == 'quoted':
        return 'Quote'
    if t == 'replied_to':
        return 'Thread' if tweet.get('in_reply_to_user_id') == author_id else 'Reply'
    return 'Original'


def _build_rows(posts: list[dict], author_id: str, tweet_map: dict, user_map: dict) -> list[dict]:
    rows = []
    for p in posts:
        refs = p.get('referenced_tweets', [])
        ref_id = refs[0]['id'] if refs else None
        ref_tweet = tweet_map.get(ref_id, {}) if ref_id else {}
        ref_text = ref_tweet.get('text', '')
        context = (ref_text[:120] + '…') if len(ref_text) > 120 else ref_text

        post_type = _post_type(p, author_id)
        if post_type in ('Reply', 'Thread'):
            u = user_map.get(p.get('in_reply_to_user_id'), {})
        elif post_type in ('Retweet', 'Quote'):
            u = user_map.get(ref_tweet.get('author_id'), {})
        else:
            u = {}
        ref_author = f"@{u['username']}" if u else ''

        raw_text = p.get('text', '')
        rows.append({
            'type': post_type,
            'created_at': _format_dt(p.get('created_at', '')),
            'text': raw_text,
            'text_segs': _segment(raw_text),
            'ref_author': ref_author,
            'context': context,
            'context_segs': _segment(context) if context else [],
            'retweet_count': p.get('public_metrics', {}).get('retweet_count', 0),
            'like_count': p.get('public_metrics', {}).get('like_count', 0),
            'reply_count': p.get('public_metrics', {}).get('reply_count', 0),
            'id': p.get('id', ''),
        })
    return rows


# ---- UI ----

TABLE_COLUMNS = [
    {'name': 'type',          'label': 'Type',        'field': 'type',          'sortable': True,  'align': 'left',  'style': 'width:80px;  min-width:80px'},
    {'name': 'created_at',    'label': 'Date',        'field': 'created_at',    'sortable': True,  'align': 'left',  'style': 'width:130px; min-width:130px'},
    {'name': 'text',          'label': 'Text',        'field': 'text',          'sortable': False, 'align': 'left'},
    {'name': 'ref_author',    'label': 'Ref. Author', 'field': 'ref_author',    'sortable': True,  'align': 'left',  'style': 'width:110px; min-width:110px'},
    {'name': 'context',       'label': 'Context',     'field': 'context',       'sortable': False, 'align': 'left'},
    {'name': 'retweet_count', 'label': 'RTs',         'field': 'retweet_count', 'sortable': True,  'align': 'right', 'style': 'width:55px;  min-width:55px'},
    {'name': 'like_count',    'label': 'Likes',       'field': 'like_count',    'sortable': True,  'align': 'right', 'style': 'width:60px;  min-width:60px'},
    {'name': 'reply_count',   'label': 'Replies',     'field': 'reply_count',   'sortable': True,  'align': 'right', 'style': 'width:70px;  min-width:70px'},
]


@ui.page('/')
def index():
    stored: dict = {}

    # ------------------------------------------------------------------ sidebar
    with ui.left_drawer(value=True, bordered=True).classes('p-5 bg-slate-50 flex flex-col gap-4'):

        ui.label('X Post Downloader').classes('text-lg font-bold text-slate-800')
        ui.separator()

        # Auth
        ui.label('Bearer Token').classes('text-xs font-semibold text-slate-500 uppercase tracking-wide')
        token_input = ui.input(
            value=os.environ.get('X_BEARER_TOKEN', '').strip(),
            password=True,
            placeholder='paste token…',
        ).classes('w-full')

        ui.separator()

        # User search
        ui.label('Look Up User').classes('text-xs font-semibold text-slate-500 uppercase tracking-wide')
        ui.label('Exact @username only — display name search requires a paid API plan.') \
          .classes('text-xs text-slate-400 leading-snug')
        search_input = ui.input(placeholder='elonmusk').props('dense outlined').classes('w-full mt-1')
        lookup_btn = ui.button('Look Up', icon='search').props('unelevated color=primary').classes('w-full')

        # User info card (shown after successful lookup)
        with ui.card().tight().classes('w-full bg-white rounded-lg hidden') as user_card:
            with ui.card_section().classes('gap-0'):
                user_display = ui.label('').classes('font-semibold text-slate-800')
                user_handle  = ui.label('').classes('text-sm text-slate-500')
                ui.separator().classes('my-2')
                user_metrics = ui.label('').classes('text-xs text-slate-600')
                user_bio     = ui.label('').classes('text-xs text-slate-500 italic mt-1')

    # ------------------------------------------------------------------ main
    with ui.column().classes('p-6 w-full gap-3'):

        # All inputs in one compact row
        with ui.row().classes('w-full gap-3 items-end flex-wrap'):
            username_input = ui.input('Username (without @)', value='elonmusk') \
                              .props('outlined dense').classes('flex-1 min-w-40')
            start_input = ui.input('Start date', value='2024-01-01') \
                           .props('type=date outlined dense').classes('w-36')
            end_input   = ui.input('End date', value=date.today().isoformat()) \
                           .props('type=date outlined dense').classes('w-36')
            max_results_input = ui.number('Max', value=500, min=10, max=3200, step=100) \
                                 .props('outlined dense').classes('w-24')
            include_refs_checkbox = ui.checkbox('Include ref. tweets').tooltip(
                'Fetches the content of replied-to/quoted/retweeted posts (Context column). Uses more API credits.'
            )
            fetch_btn = ui.button('Fetch', icon='cloud_download') \
                         .props('unelevated color=primary')

        # Progress + status
        progress = ui.linear_progress(show_value=False).classes('w-full').set_visibility(False)
        status   = ui.label('').classes('text-sm text-slate-400')

        # Results table (hidden until data arrives)
        table = ui.table(
            columns=TABLE_COLUMNS,
            rows=[],
            row_key='id',
            pagination={'rowsPerPage': 25, 'rowsPerPageOptions': [10, 25, 50, 100]},
        ).classes('w-full shadow-sm').set_visibility(False)

        # Render text with clickable @mentions (→ username field) and URLs (→ new tab)
        table.add_slot('body-cell-text', r'''
            <q-td :props="props" style="white-space:normal; min-width:200px;">
                <span style="word-break:break-word; line-height:1.4">
                    <template v-for="seg in props.row.text_segs">
                        <a v-if="seg.t === 'url'"
                           :href="seg.v" target="_blank"
                           style="color:#3b82f6">{{seg.v}}</a>
                        <a v-else-if="seg.t === 'mention'"
                           href="#"
                           style="color:#3b82f6; cursor:pointer; font-weight:500"
                           @click.prevent="$parent.$emit('setUsername', seg.v)">@{{seg.v}}</a>
                        <span v-else>{{seg.v}}</span>
                    </template>
                </span>
            </q-td>
        ''')

        table.add_slot('body-cell-context', r'''
            <q-td :props="props" style="white-space:normal; min-width:150px;">
                <span style="word-break:break-word; line-height:1.4; color:#6b7280; font-style:italic">
                    <template v-for="seg in props.row.context_segs">
                        <a v-if="seg.t === 'url'"
                           :href="seg.v" target="_blank"
                           style="color:#3b82f6; font-style:normal">{{seg.v}}</a>
                        <a v-else-if="seg.t === 'mention'"
                           href="#"
                           style="color:#3b82f6; cursor:pointer; font-weight:500; font-style:normal"
                           @click.prevent="$parent.$emit('setUsername', seg.v)">@{{seg.v}}</a>
                        <span v-else>{{seg.v}}</span>
                    </template>
                </span>
            </q-td>
        ''')

        # Make ref_author a clickable chip — emits 'clickAuthor' to Python
        table.add_slot('body-cell-ref_author', r'''
            <q-td :props="props">
                <q-btn v-if="props.row.ref_author"
                       flat dense no-caps size="sm" color="primary"
                       :label="props.row.ref_author"
                       @click.stop="$parent.$emit('clickAuthor', props.row.ref_author)" />
                <span v-else class="text-grey-4">—</span>
            </q-td>
        ''')

        # Download buttons (hidden until data arrives)
        with ui.row().classes('gap-2') as dl_row:
            json_btn = ui.button('Download JSON', icon='download').props('flat color=primary')
            csv_btn  = ui.button('Download CSV',  icon='download').props('flat color=primary')
        dl_row.set_visibility(False)

        ui.label("Built with NiceGUI + Twarc2 · Respect X's terms of service · ~3200 most recent posts max") \
          .classes('text-xs text-slate-400 mt-2')

    # ------------------------------------------------------------------ handlers

    async def on_lookup():
        token = token_input.value.strip()
        query = search_input.value.strip().lstrip('@')
        if not token:
            ui.notify('Enter your Bearer Token first.', type='warning')
            return
        if not query:
            ui.notify('Enter a username.', type='warning')
            return
        if ' ' in query:
            ui.notify('Display name search not available on free tier.', type='warning')
            return
        try:
            client = _get_client(token)
            u = await run.io_bound(_lookup_user, client, query)
            if not u:
                ui.notify(f'@{query} not found.', type='negative')
                return
            # Populate sidebar card
            m = u.get('public_metrics', {})
            desc = (u.get('description') or '').strip()
            user_display.text = u.get('name', '')
            user_handle.text  = f"@{u['username']}"
            user_metrics.text = (
                f"{m.get('followers_count', 0):,} followers · "
                f"{m.get('tweet_count', 0):,} posts"
            )
            user_bio.text = desc[:200] + ('…' if len(desc) > 200 else '')
            user_bio.set_visibility(bool(desc))
            user_card.classes(remove='hidden')
            # Pre-fill the username field
            username_input.value = u['username']
        except Exception as e:
            ui.notify(f'Lookup error: {e}', type='negative')

    async def on_fetch():
        token = token_input.value.strip()
        uname = username_input.value.strip()
        if not token:
            ui.notify('Enter your Bearer Token.', type='warning')
            return
        if not uname:
            ui.notify('Enter a username.', type='warning')
            return
        try:
            start = date.fromisoformat(start_input.value)
            end   = date.fromisoformat(end_input.value)
        except ValueError:
            ui.notify('Invalid date.', type='warning')
            return
        if end < start:
            ui.notify('End date must be after start date.', type='warning')
            return

        table.set_visibility(False)
        dl_row.set_visibility(False)
        progress.set_visibility(True)
        progress.value = 0.1
        status.text = f'Looking up @{uname}…'

        try:
            client = _get_client(token)
            user = await run.io_bound(_lookup_user, client, uname)
            if not user:
                ui.notify('User not found or account is private.', type='negative')
                status.text = ''
                progress.set_visibility(False)
                return

            progress.value = 0.3
            status.text = f'Fetching posts for @{uname}…'

            posts, tweet_map, user_map, truncated = await run.io_bound(
                _fetch_timeline, client, user['id'], start, end, int(max_results_input.value), include_refs_checkbox.value
            )

            if not posts:
                ui.notify(f'No posts found for @{uname} in the selected date range.', type='warning')
                status.text = ''
                progress.set_visibility(False)
                return

            stored.update({
                'posts': posts,
                'author_id': user['id'],
                'tweet_map': tweet_map,
                'user_map': user_map,
                'meta': {'username': uname, 'start': start, 'end': end},
            })

            table.rows = _build_rows(posts, user['id'], tweet_map, user_map)
            table.update()
            progress.value = 1.0
            if truncated:
                status.text = f'{len(posts):,} posts fetched for @{uname} (partial — API usage cap hit)'
                ui.notify(
                    f'Showing {len(posts):,} posts retrieved before the usage cap was hit. '
                    'Credits for those posts were already consumed.',
                    type='warning',
                    timeout=8000,
                )
            else:
                status.text = f'{len(posts):,} posts fetched for @{uname}'
            table.set_visibility(True)
            dl_row.set_visibility(True)

        except Exception as e:
            ui.notify(f'Error: {e}', type='negative')
            status.text = ''
            progress.set_visibility(False)

    def on_set_username(e):
        username = (e.args or '').lstrip('@')
        if username:
            username_input.value = username

    def on_author_click(e):
        ref = (e.args or '').lstrip('@')
        if ref:
            username_input.value = ref

    def on_download_json():
        posts = stored.get('posts', [])
        meta  = stored.get('meta', {})
        if not posts:
            return
        ui.download(
            json.dumps(posts, indent=2, ensure_ascii=False).encode('utf-8'),
            f"{meta['username']}_posts_{meta['start']}_{meta['end']}.json",
        )

    def on_download_csv():
        posts = stored.get('posts', [])
        meta  = stored.get('meta', {})
        if not posts:
            return
        df = pd.DataFrame(_build_rows(
            posts, stored['author_id'], stored['tweet_map'], stored['user_map']
        )).drop(columns=['text_segs', 'context_segs'], errors='ignore')
        buf = BytesIO()
        df.to_csv(buf, index=False, encoding='utf-8')
        ui.download(buf.getvalue(), f"{meta['username']}_posts_{meta['start']}_{meta['end']}.csv")

    # ------------------------------------------------------------------ wire up
    lookup_btn.on('click', on_lookup)
    fetch_btn.on('click', on_fetch)
    table.on('setUsername', on_set_username)
    table.on('clickAuthor', on_author_click)
    json_btn.on('click', on_download_json)
    csv_btn.on('click', on_download_csv)


ui.run(title='X Post Downloader', port=8080, reload=False)
