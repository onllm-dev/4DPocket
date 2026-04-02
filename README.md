# 4DPocket

> *"Reach into your pocket and pull out exactly what you need."*

Self-hosted, AI-powered personal knowledge base. Save content from 15+ platforms, let AI organize and connect it, and find anything instantly.

## Features

- **Universal Capture** — Save URLs, notes, images, PDFs. Supports YouTube, Reddit, GitHub, Twitter/X, Instagram, and more.
- **AI-Powered Organization** — Auto-tagging with confidence scores, smart tag hierarchy, auto-summarization.
- **Powerful Search** — Full-text search (SQLite FTS5 or Meilisearch) + semantic vector search (ChromaDB).
- **Related Items** — AI finds connections between your saved knowledge using semantic similarity, shared tags, and source analysis.
- **Multi-Provider AI** — Works with Ollama (local), Groq, or NVIDIA APIs. No vendor lock-in.
- **PWA Frontend** — React + TypeScript + Tailwind CSS. Responsive, dark mode, installable.
- **Zero-Config Local Mode** — `uv run` and go. SQLite for everything. No Docker required.
- **Docker Ready** — Full stack with PostgreSQL, Meilisearch, ChromaDB, Ollama.

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

Open http://localhost:5173 — no login needed in single-user mode.

### Docker

```bash
cp .env.example .env
# Edit .env with your API keys (optional)
docker compose up
```

Open http://localhost:4040

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI, SQLModel, Alembic, Python 3.12+ |
| **Database** | SQLite (default) / PostgreSQL |
| **Search** | SQLite FTS5 (default) / Meilisearch |
| **Vector DB** | ChromaDB (in-process) |
| **AI** | Ollama / Groq / NVIDIA (OpenAI-compatible) |
| **Embeddings** | sentence-transformers (local) / NVIDIA nv-embed-v1 |
| **Background Jobs** | Huey (SQLite backend) |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS v4 |
| **State** | TanStack Query (server) + Zustand (client) |
| **Icons** | Lucide React |

## Content Processors

| Platform | What's Extracted |
|----------|-----------------|
| **Generic URL** | Title, description, article content (readability), OG metadata, favicon |
| **YouTube** | Title, channel, duration, transcript, chapters, thumbnails |
| **Reddit** | Post title, selftext, top 10 comments, subreddit, score |
| **GitHub** | Repo metadata, README, stars, issues/PRs with comments, gists |
| **Twitter/X** | Tweet text, author, media, engagement stats (via fxtwitter) |
| **Instagram** | Caption, images/carousel, hashtags (via instaloader) |
| **Image** | EXIF data, OCR text extraction |
| **PDF** | Full text, metadata, page count |

## Configuration

All config via environment variables with `FDP_` prefix. See [`.env.example`](.env.example) for all options.

Key settings:

```bash
# AI Provider: "ollama", "groq", or "nvidia"
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
| `POST /api/v1/auth/register` | Register user |
| `POST /api/v1/auth/login` | Login (returns JWT) |
| Full CRUD | Items, Notes, Tags, Collections |

## Project Structure

```
4dpocket/
├── src/fourdpocket/          # Python backend
│   ├── api/                  # FastAPI endpoints
│   ├── models/               # SQLModel database models
│   ├── processors/           # Content extractors (8 platforms)
│   ├── ai/                   # AI providers + tagging + summarization
│   ├── search/               # FTS5 + Meilisearch + ChromaDB semantic
│   ├── workers/              # Huey background tasks
│   └── storage/              # File storage (user-scoped)
├── frontend/                 # React PWA
│   └── src/
│       ├── pages/            # 9 page components
│       ├── components/       # Layout, BookmarkCard, BookmarkForm
│       ├── hooks/            # TanStack Query data hooks
│       └── stores/           # Zustand UI state
├── tests/                    # pytest test suite (55+ tests)
├── Dockerfile               # Multi-stage Python build
├── docker-compose.yml       # Full stack orchestration
└── .env.example             # Configuration reference
```

## Development

```bash
# Run tests
make test

# Run with coverage
make test-cov

# Lint
make lint

# Format
make format

# Generate migration
make migrate-gen msg="description"

# Apply migrations
make migrate
```

## License

MIT

---

Built with ❤️ by [onllm.dev](https://onllm.dev)

[onllm.dev](https://onllm.dev) · [GitHub](https://github.com/onllm-dev/4DPocket) · [Support 4DPocket](https://buymeacoffee.com/prakersh)
