# X Post Downloader

A desktop web app for downloading and browsing posts from any public X (Twitter) account. Built with [NiceGUI](https://nicegui.io) and [Twarc2](https://twarc-project.readthedocs.io).

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

---

## Features

- Browse and download posts for any public X account
- Filter by date range
- Rich results table with:
  - Post type (Original / Reply / Thread / Quote / Retweet)
  - Local-timezone timestamps
  - Clickable @mentions — click any username to set it as the next search target
  - Clickable URLs — open in a new tab
  - Optional referenced tweet context (replied-to / quoted / retweeted content)
- Export results as **JSON** (full API response) or **CSV** (summary)
- User lookup by exact @username with profile card (followers, bio)
- Bearer token can be pre-loaded from an environment variable

---

## Prerequisites

- **Python 3.10 or higher** — [python.org](https://python.org)
- An **X Developer account** with a project app and a **Bearer Token**
  - Sign up at [developer.x.com](https://developer.x.com)
  - Requires a paid plan or prepaid credit balance — X no longer offers a free API tier

---

## Installation

### macOS / Linux

```bash
git clone https://github.com/your-username/x-downloader.git
cd x-downloader
./install.sh
```

### Windows

```bat
git clone https://github.com/your-username/x-downloader.git
cd x-downloader
install.bat
```

---

## Configuration

The app will prompt you to enter your Bearer Token in the sidebar on each launch. To avoid this, set it as an environment variable.

**Option 1 — shell profile (persistent across terminals):**

```bash
# macOS/Linux — add to ~/.zshrc or ~/.bashrc
export X_BEARER_TOKEN=your_token_here
```

```bat
:: Windows — set via System Properties > Environment Variables
:: or in the current session:
set X_BEARER_TOKEN=your_token_here
```

**Option 2 — `.env` file in the project folder:**

Create a file named `.env` in the project root:

```
X_BEARER_TOKEN=your_token_here
```

The run scripts will pick this up automatically. The `.env` file is excluded from version control by `.gitignore` — never commit it.

---

## Running

### macOS / Linux

```bash
./run.sh
```

### Windows

```bat
run.bat
```

Then open [http://localhost:8080](http://localhost:8080) in your browser.

---

## Usage

### Looking up a user

Use the **Look Up User** panel in the sidebar to find an account by exact @username. Display name search is not available on the free X API tier. After a successful lookup the sidebar shows the account's name, follower count, and bio, and pre-fills the username field.

### Fetching posts

Fill in the form at the top of the page:

| Field | Description |
|---|---|
| **Username** | X handle without the `@` |
| **Start / End date** | Date range to fetch posts from |
| **Max posts** | Maximum number of posts to retrieve (up to 3200) |
| **Include ref. tweets** | Also fetch the content of replied-to, quoted, and retweeted posts. Costs additional API reads — leave unchecked unless you need the Context column. |

Click **Fetch** to retrieve posts. Results appear in the table below with pagination (25 / 50 / 100 rows per page).

### Navigating results

- Click any **@mention** in the Text or Context column to set that user as the next fetch target.
- Click a **Ref. Author** button to do the same from the reference column.
- Click any **URL** to open it in a new tab.

### Exporting

Once posts are loaded, two download buttons appear:

- **Download JSON** — the full raw API response for each post, including all fields.
- **Download CSV** — a flat summary with type, date, text, ref author, context, and engagement metrics.

---

## API usage and costs

X API costs are driven by **tweet reads** — each post fetched counts against your monthly quota. A few things to be aware of:

- **Max 3200 posts** per account (X API limitation on user timelines).
- The **Include ref. tweets** checkbox enables the `referenced_tweets.id` expansion, which fetches referenced tweet objects and counts them as additional reads. Leave it off if you only need the post type and text.
- User lookups (`Look Up User`) consume a small number of reads per search.
- X no longer offers a free API tier. Access requires a paid plan (Basic at $100/month) or a prepaid credit balance. See [developer.x.com](https://developer.x.com) for current pricing.
- If you hit your credit limit mid-fetch, the app will display however many posts were successfully retrieved before the cap was reached.

---

## Project structure

```
x-downloader/
├── x-downloader-app.py   # Main application
├── requirements.txt       # Python dependencies
├── install.sh             # macOS/Linux install script
├── run.sh                 # macOS/Linux run script
├── install.bat            # Windows install script
└── run.bat                # Windows run script
```

---

## License

MIT
