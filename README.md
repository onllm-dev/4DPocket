<p align="center">
  <img src="frontend/public/icons/icon.svg" width="80" alt="4DPocket" />
</p>

<h1 align="center">4DPocket</h1>

<p align="center">
  <em>"Reach into your pocket and pull out exactly what you need."</em>
</p>

<p align="center">
  <strong>Self-hosted, AI-powered personal knowledge base</strong><br/>
  Inspired by Doraemon's 4D Pocket - a magical, bottomless pocket where anything you've ever saved is instantly retrievable.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-active%20development-brightgreen" alt="Active Development" />
  <img src="https://img.shields.io/badge/license-GNU%20GPLv3-blue" alt="GNU GPLv3 License" />
</p>

> **This project is in active development and is being updated regularly.** New features, processors, and improvements ship frequently. Star the repo to stay updated!

<p align="center">
  <a href="https://github.com/onllm-dev/4DPocket">GitHub</a> · <a href="https://onllm.dev">onllm.dev</a> · <a href="https://buymeacoffee.com/prakersh">Support 4DPocket</a>
</p>

---

## The Idea

Everyone saves things - bookmarks, articles, videos, code snippets, social media posts - across dozens of platforms. Then can never find them again.

**4DPocket** is different. It's not a bookmark manager - it's a **magic library**. Throw anything in - URLs, notes, YouTube videos, Reddit threads, GitHub repos, tweets, PDFs, images - and the pocket **understands** it, **connects** it to what you already know, and **serves** it back when you need it.

Just like Doraemon reaches into his 4D Pocket and pulls out the perfect gadget for any situation, you reach into yours and pull out exactly the knowledge you need.

### Core Philosophy

| Principle | What It Means |
|-----------|--------------|
| **Knowledge-First** | Every item is extracted, enriched, indexed, and connected. Your pocket *understands* what's inside it. |
| **Retrieval-First** | Everything is designed around getting things *out* fast. Search is instant, smart, and forgiving. |
| **Local-First** | Runs entirely on your machine by default. Your data never leaves unless you choose external APIs. |
| **Zero-Friction Capture** | Save anything in 1-2 actions. Paste a URL and everything is handled automatically. |
| **Smart by Default** | AI auto-tags, auto-summarizes, auto-connects. You don't organize - the pocket organizes itself. |
| **Private by Default** | Each user's knowledge base is their own. Sharing is explicit, granular, and revocable. |

---

## Features

### Universal Capture - 17 Platform Processors

Save a URL and 4DPocket automatically detects the platform and deeply extracts content - not just metadata, but the actual knowledge.

| Platform | What's Extracted |
|----------|-----------------|
| **Generic URL** | Title, description, full article content (readability), OG metadata, favicon |
| **YouTube** | Title, channel, duration, full transcript, chapters, thumbnails |
| **Reddit** | Post title, selftext, top 10 comments, subreddit, score |
| **GitHub** | Repo metadata, README content, stars, language, issues/PRs with comments, gists |
| **Twitter/X** | Tweet text, author, media attachments, engagement stats (via fxtwitter) |
| **Instagram** | Caption, images/carousel, hashtags, alt text (via instaloader) |
| **Hacker News** | Title, author, score, top comments tree (via Algolia API) |
| **Stack Overflow** | Question, accepted answer, top answers, tags, code blocks |
| **TikTok** | Description, author, thumbnail, hashtags, view count (via yt-dlp) |
| **Threads** | Author, content, media (OG metadata extraction) |
| **Mastodon** | Toot content, media, boosts, favourites (auto-detects instance) |
| **Substack** | Full article text, author, newsletter name (readability) |
| **Medium** | Full article text, author, publication (readability) |
| **LinkedIn** | Post text, author (public posts only) |
| **Spotify** | Track/album/playlist name, artist, cover art (oEmbed API) |
| **Image** | EXIF data, OCR text extraction (pytesseract) |
| **PDF** | Full text extraction, metadata, page count (PyMuPDF) |

### AI-Powered Smart Organization

The brain of 4DPocket - what transforms it from a link saver into a knowledge base that thinks.

- **Auto-Tagging** - AI reads extracted content and assigns tags with confidence scores (0-1). High-confidence tags are applied automatically, lower ones are suggested.
- **Smart Tag Hierarchy** - Tags auto-organize into parent-child trees. `python` nests under `programming/python`, `react` under `frontend/react`.
- **Auto-Summarization** - Every saved item gets a 2-3 sentence AI summary.
- **Related Items** - The moment you save something, 4DPocket shows you what's related in your library using semantic similarity (0.5 weight), shared tags (0.3), and same-source analysis (0.2).
- **Multi-Provider AI** - Works with Ollama (local), Groq, NVIDIA, or any OpenAI/Anthropic-compatible API (MiniMax, Together, Fireworks, OpenRouter, etc.). No vendor lock-in.
- **Sync Enrichment** - AI enriches items inline when saved, even without a background worker running. Tags + summaries appear immediately.
- **Prompt Injection Protection** - All user content is sanitized before reaching AI models. XML delimiters isolate user data from system instructions.

### Powerful Search

- **Full-Text Search** - SQLite FTS5 (zero-config) or Meilisearch (optional upgrade). Typo-tolerant, instant results.
- **Semantic Search** - Vector similarity search using sentence-transformers + ChromaDB. Find "that article about React performance" even if those exact words aren't in the title.
- **Search Filters** - Filter by platform, content type, tags, date ranges. Command palette (Cmd+K) for instant access.

### Multi-User Knowledge Bases

Every user gets their own isolated pocket. Knowledge is private by default, shareable by choice.

- **Per-User Isolation** - Items, tags, collections, AI enrichments are all scoped to the user.
- **Selective Sharing** - Share individual items, entire collections, or tag-based groups with specific users.
- **Public Links** - Generate public URLs for sharing outside your instance (with optional expiry).
- **Knowledge Feeds** - Follow other users' public items. Their saves appear in your feed.
- **Comments** - Discuss shared items with collaborators.
- **Roles** - Admin (full instance management), User (full knowledge base), Guest (view shared only).

### Admin Control Panel

- **User Management** - List, activate/deactivate, change roles for all users.
- **Registration Control** - Toggle registration on/off, set mode (open/invite/disabled).
- **Instance Settings** - Configure instance name, default user role, max users.
- **AI Configuration** - Change AI provider, API keys, model, base URL from the admin panel. Admin settings override .env values at runtime.

### Automation Rules

- **Condition-Action Rules** - "If saved from reddit.com, auto-tag 'reddit' and add to 'Reddit Saves' collection."
- **CRUD API** - Create, read, update, delete rules via REST API.

### Import & Export

- **Import From** - Chrome bookmarks (HTML), Pocket export (HTML), generic JSON.
- **Export To** - JSON, HTML bookmarks (Netscape format), CSV, Markdown.

### PWA - Works Everywhere

4DPocket is a Progressive Web App. Install it on any device.

- **Installable** - Add to home screen on Android, iOS, desktop.
- **Offline Support** - Service worker caches static assets for offline access.
- **Share Target** - Share URLs directly from your phone's share sheet to 4DPocket.
- **Responsive** - Optimized for mobile (bottom nav, touch-friendly), tablet (collapsible sidebar), and desktop (full sidebar, keyboard shortcuts).
- **Dark Mode** - System-aware with manual toggle.

### Browser Extensions (Coming Soon)

- **Chrome** - Save pages, highlights, and selections with one click.
- **Firefox** - Full extension support with context menu integration.
- **Safari** - Native Safari extension for macOS and iOS.

### Native Apps (Coming Soon)

- **Android** - Native Android app with share intent integration and offline support.
- **iOS** - Native iOS app with share extension and widget support.

### Keyboard-First UX

- **Command Palette** - `Cmd+K` / `Ctrl+K` to search anything, navigate pages, find items instantly.
- **Shortcuts** - `n` to add new item, `/` to open search.
- **Bulk Actions** - Select multiple items, then bulk tag, archive, or delete.

---

## Quick Start

### Local (Zero Config)

```bash
# Clone
git clone https://github.com/onllm-dev/4DPocket.git
cd 4DPocket

# Install & run backend
uv sync --all-extras
uv run uvicorn fourdpocket.main:app --port 4040

# Install & run frontend (separate terminal)
cd frontend
pnpm install
pnpm dev
```

Open http://localhost:5173 - no login needed in single-user mode.

### Docker

```bash
cp .env.example .env
# Edit .env with your API keys (optional)
docker compose up
```

Open http://localhost:4040

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI, SQLModel, Alembic, Python 3.12+ |
| **Database** | SQLite (default) / PostgreSQL |
| **Search** | SQLite FTS5 (default) / Meilisearch |
| **Vector DB** | ChromaDB (in-process) |
| **AI** | Ollama / Groq / NVIDIA / Custom (OpenAI or Anthropic-compatible) |
| **Embeddings** | sentence-transformers (local) / NVIDIA nv-embed-v1 |
| **Background Jobs** | Huey (SQLite backend) |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS v4 |
| **State** | TanStack Query (server) + Zustand (client) |
| **Icons** | Lucide React |

## Configuration

All config via environment variables with `FDP_` prefix. See [`.env.example`](.env.example) for all options.

```bash
# AI Provider: "ollama", "groq", "nvidia", or "custom"
FDP_AI__CHAT_PROVIDER=ollama

# Search Backend: "sqlite" (zero-config) or "meilisearch"
FDP_SEARCH__BACKEND=sqlite

# Auth Mode: "single" (no login) or "multi" (JWT)
FDP_AUTH__MODE=single
```

## API

Interactive docs at http://localhost:4040/docs when running.

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/items` | Save a URL or note |
| `GET /api/v1/items` | List items (paginated, filtered) |
| `GET /api/v1/search?q=...` | Full-text search |
| `GET /api/v1/search/semantic?q=...` | Semantic vector search |
| `GET /api/v1/search/filters` | Available filter facets |
| `POST /api/v1/items/bulk` | Bulk tag, archive, delete |
| `GET /api/v1/items/{id}/related` | AI-suggested related items |
| `POST /api/v1/auth/register` | Register user |
| `POST /api/v1/auth/login` | Login (returns JWT) |
| `GET/PATCH /api/v1/settings` | User preferences |
| `GET /api/v1/stats` | Dashboard statistics |
| `POST/GET/DELETE /api/v1/shares` | Sharing management |
| `GET /api/v1/feeds` | Knowledge feed |
| `POST /api/v1/import/{source}` | Import bookmarks |
| `GET /api/v1/export/{format}` | Export data |
| `GET/POST/PATCH/DELETE /api/v1/rules` | Automation rules |
| Full CRUD | Items, Notes, Tags, Collections, Comments |

## Project Structure

```
4dpocket/
├── src/fourdpocket/          # Python backend
│   ├── api/                  # FastAPI endpoints (19 routers)
│   ├── models/               # SQLModel database models
│   ├── processors/           # Content extractors (17 platforms)
│   ├── ai/                   # AI providers + tagging + summarization + sanitizer
│   ├── search/               # FTS5 + Meilisearch + ChromaDB semantic
│   ├── sharing/              # Share manager, permissions, feed manager
│   ├── workers/              # Huey background tasks
│   └── storage/              # File storage (user-scoped)
├── frontend/                 # React PWA
│   └── src/
│       ├── pages/            # 21 page components
│       ├── components/       # Layout, BookmarkCard, ShareDialog, CommandPalette
│       ├── hooks/            # TanStack Query data hooks + keyboard shortcuts
│       └── stores/           # Zustand UI state
├── tests/                    # pytest test suite (65+ tests)
├── Dockerfile               # Multi-stage Python build
├── docker-compose.yml       # Full stack orchestration
└── .env.example             # Configuration reference
```

## Development

```bash
# Run tests
make test

# Lint
make lint

# Format
make format

# Generate migration
make migrate-gen msg="description"
```

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with &#10084; by <a href="https://onllm.dev">onllm.dev</a>
</p>

<p align="center">
  <a href="https://onllm.dev">onllm.dev</a> · <a href="https://github.com/onllm-dev/4DPocket">GitHub</a> · <a href="https://buymeacoffee.com/prakersh">Support 4DPocket</a>
</p>
