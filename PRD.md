# 4DPocket — Product Requirements Document (PRD)

> *"Reach into your pocket and pull out exactly what you need."*
> Inspired by Doraemon's 4D Pocket — a magical, bottomless pocket where anything you've ever saved is instantly retrievable.

---

## 1. Vision & Philosophy

**4DPocket** is a self-hosted, AI-powered **personal knowledge base** built in Python. It's not a bookmark manager — it's a **magic library** where every piece of knowledge you encounter on the internet gets captured, understood, connected, and made retrievable on demand.

Throw anything in — URLs, notes, YouTube videos, Instagram posts, Reddit threads, GitHub projects, tweets, Threads posts, TikToks, Hacker News discussions, images, PDFs — and the pocket **understands** it, **connects** it to what you already know, and **serves** it back when you need it.

Each user gets their own knowledge base. Knowledge is private by default, but users can selectively share individual items, collections, or entire knowledge domains with other users — turning personal knowledge into collaborative intelligence.

### Core Principles

| Principle | Description |
|---|---|
| **Knowledge-First** | This is not a link dumping ground. Every item is extracted, enriched, indexed, and connected. Your pocket *understands* what's inside it. |
| **Retrieval-First** | Everything is designed around getting things *out* fast. Search is instant, smart, and forgiving (typos, fuzzy, semantic). |
| **Local-First** | Runs entirely on your machine by default. Your data never leaves unless you choose to use external APIs. |
| **Zero-Friction Capture** | Save anything in 1-2 actions. Browser extension, share sheet, API, CLI — every surface is a pocket entrance. |
| **Smart by Default** | AI auto-tags, auto-categorizes, auto-summarizes, auto-connects. You don't organize — the pocket organizes itself. |
| **Private by Default, Shareable by Choice** | Each user's knowledge base is their own. Sharing is explicit, granular, and revocable. |
| **PWA-Native** | One codebase, works beautifully on desktop, tablet, and phone. Installable, offline-capable, responsive. |

---

## 2. Target Users

- **Knowledge workers** who consume content across dozens of platforms and need it all in one searchable, connected place
- **Developers** who collect GitHub repos, Stack Overflow answers, blog posts, documentation, and technical threads
- **Researchers** who collect articles, papers, YouTube lectures, Reddit discussions, and Twitter/X threads
- **Content creators** who hoard inspiration, references, and ideas from Instagram, TikTok, YouTube, and the wider web
- **Teams & couples** who want to selectively share knowledge — "hey, check out what I saved about X"
- **Anyone** who saves things across 15 different platforms and can never find them again

---

## 3. Content Types Supported

### 3.1 Platform-Specific Content

| Content Type | Capture Method | Metadata Extracted |
|---|---|---|
| **URL / Webpage** | Paste URL, browser extension, share sheet | Title, description, OG image, favicon, full-page archive, screenshot |
| **Note** | Quick note editor (markdown) | Tags (AI), summary (AI) |
| **YouTube Video** | Paste YT URL | Title, thumbnail, channel, duration, transcript, chapters, comments |
| **YouTube Short** | Paste YT Shorts URL | Same as video, flagged as short-form |
| **Instagram Post** | Paste IG URL | Author, caption, images/carousel, hashtags, alt text, likes |
| **Instagram Reel** | Paste IG Reel URL | Author, caption, video thumbnail, audio info, hashtags |
| **Instagram Story** | Paste IG Story URL (when available) | Author, media, timestamp, interactive elements |
| **Reddit Post** | Paste Reddit URL | Title, subreddit, score, top comments, media, crosspost info |
| **Reddit Comment** | Paste Reddit comment permalink | Comment text, context chain, parent post title, subreddit |
| **Twitter/X Post** | Paste URL | Author, content, media, engagement stats, thread context |
| **Twitter/X Thread** | Paste thread URL | Full thread unrolled, author, media per tweet, engagement |
| **Threads Post** | Paste threads.net URL | Author, content, media, replies |
| **TikTok Video** | Paste TikTok URL | Author, description, video thumbnail, audio, hashtags, stats |
| **GitHub Repo** | Paste GH URL | Repo name, description, stars, language, README summary, topics |
| **GitHub Issue/PR** | Paste GH issue/PR URL | Title, body, labels, status, comments, linked PRs/issues |
| **GitHub Gist** | Paste Gist URL | Files, descriptions, language detection |
| **Hacker News** | Paste HN URL | Title, author, score, top comments, linked article |
| **Stack Overflow** | Paste SO URL | Question, accepted answer, top answers, tags, score |
| **Mastodon/Fediverse** | Paste toot URL | Author, content, media, boosts, instance info |
| **LinkedIn Post** | Paste LinkedIn URL | Author, content, engagement (when accessible) |
| **Substack Article** | Paste Substack URL | Title, author, publication, full article text, newsletter info |
| **Medium Article** | Paste Medium URL | Title, author, publication, full text (bypasses paywall via archive) |
| **Spotify** | Paste Spotify URL | Track/album/playlist name, artist, cover art, track listing |
| **Image** | Upload / paste | OCR text extraction, AI description, EXIF data |
| **PDF** | Upload | Full-text extraction, title, page count, summary |
| **Code Snippet** | Editor with syntax highlighting | Language detection, tags |

### 3.2 Content Extraction Philosophy

Every platform is treated as a **knowledge source**, not just a link. When you save an Instagram post, 4DPocket doesn't just store the URL — it extracts the caption, downloads the images, reads the hashtags, and indexes everything so you can search "that recipe with avocado someone posted" and find it.

**Extraction Principles:**
- **Extract everything indexable** — captions, transcripts, alt text, comments, descriptions
- **Archive the media** — images, thumbnails, video (optional), so content survives deletion
- **Preserve context** — who posted it, where, when, what thread/conversation it was part of
- **Respect rate limits & ToS** — use official APIs where available, fall back to ethical scraping, never spam
- **Degrade gracefully** — if a platform blocks extraction, still save the URL with whatever metadata is available

---

## 4. Feature Specification

### 4.1 Core Features (MVP — Phase 1)

#### 4.1.1 Universal Capture
- **URL Bookmark Engine**: Paste any URL → automatic metadata fetch (title, description, OG image, favicon)
- **Full-Page Archival**: Save complete HTML snapshots using `monolith` or `single-file` to prevent link rot
- **Screenshot Capture**: Headless browser (Playwright) captures page screenshots on save
- **Note Editor**: Markdown editor with live preview for quick notes
- **Quick Add**: Global shortcut / floating button for instant capture

#### 4.1.2 Smart Content Processors

Each content type gets a specialized processor. The system uses a **plugin-based processor registry** — adding a new platform means adding one processor class, not changing core logic.

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  User Input  │────▶│  Content Router   │────▶│  Processor Registry  │
│  (URL/Note/  │     │  (URL pattern     │     │  (plugin-based)      │
│   Upload)    │     │   matching)       │     └──────────┬──────────┘
└─────────────┘     └──────────────────┘                  │
                                                 ┌────────▼────────┐
                                                 │  Type Processor  │
                                                 │  (platform-      │
                                                 │   specific)      │
                                                 └────────┬────────┘
                                                          │
                                              ┌───────────▼───────────┐
                                              │  Extraction Pipeline   │
                                              │  1. Metadata fetch     │
                                              │  2. Content extract    │
                                              │  3. Media download     │
                                              │  4. AI enrichment      │
                                              │  5. Index & embed      │
                                              └───────────────────────┘
```

**Processor Registry & Routing:**

The Content Router matches incoming URLs against registered processor patterns. Each processor declares which URL patterns it handles. Matching is priority-ordered (most specific pattern wins). Unknown URLs fall through to the Generic URL Processor.

```python
# Example: processor registration pattern
class InstagramProcessor(BaseProcessor):
    url_patterns = [
        r"instagram\.com/p/[\w-]+",        # Posts
        r"instagram\.com/reel/[\w-]+",      # Reels
        r"instagram\.com/stories/[\w-]+",   # Stories
    ]
    content_types = ["instagram_post", "instagram_reel", "instagram_story"]
```

**Platform Processors:**

| Processor | URL Patterns | Extraction Strategy | Key Libraries |
|---|---|---|---|
| **YouTube** | `youtube.com/watch`, `youtu.be/`, `youtube.com/shorts/` | Metadata via `yt-dlp`, transcripts via `youtube-transcript-api`, chapters, comments. Optional video download. | `yt-dlp`, `youtube-transcript-api` |
| **Instagram** | `instagram.com/p/`, `/reel/`, `/stories/` | Uses `instaloader` for public posts: caption, images/carousel, hashtags, alt text. For private content, supports session cookie auth. | `instaloader` |
| **Reddit** | `reddit.com/r/*/comments/`, `old.reddit.com/`, `redd.it/` | Append `.json` to URL for API-free extraction. Post + top N comments, media, crosspost chain. | `httpx` (no API key needed) |
| **Twitter/X** | `twitter.com/*/status/`, `x.com/*/status/` | Uses `nitter` instances or `gallery-dl` for extraction. Full thread unrolling for thread URLs. Fallback: `FixTweet` API. | `gallery-dl`, `httpx` |
| **Threads** | `threads.net/@*/post/` | Scrape via headless browser (Playwright) — no public API. Extract author, text, media, replies. | `playwright`, `httpx` |
| **TikTok** | `tiktok.com/@*/video/`, `vm.tiktok.com/` | Uses `yt-dlp` (supports TikTok). Extract description, video thumbnail, audio, hashtags, stats. Optional video download. | `yt-dlp` |
| **GitHub** | `github.com/*/*`, `/issues/`, `/pull/`, `gist.github.com/` | GitHub REST API (with optional token for rate limits). Repos: README + metadata. Issues/PRs: body + comments + labels. | `httpx`, GitHub API |
| **Hacker News** | `news.ycombinator.com/item?id=` | HN Algolia API for item + comments tree. Also fetches the linked article via Generic URL Processor. | `httpx`, HN API |
| **Stack Overflow** | `stackoverflow.com/questions/` | SE API: question + accepted answer + top answers + tags + code blocks. | `httpx`, SE API |
| **Mastodon** | `*/@ */\d+` (ActivityPub URLs) | Mastodon API: toot content, media, boosts. Auto-detects instance from URL. | `httpx`, Mastodon API |
| **Substack** | `*.substack.com/p/` | Full article extraction via readability. Newsletter + author metadata. | `httpx`, `readability-lxml` |
| **Medium** | `medium.com/`, `*.medium.com/` | Readability extraction. Falls back to Freedium/Scribe for paywalled content. | `httpx`, `readability-lxml` |
| **LinkedIn** | `linkedin.com/posts/`, `/pulse/` | Limited extraction (public posts only). Author, text content, engagement when available. | `httpx`, `playwright` |
| **Spotify** | `open.spotify.com/track/`, `/album/`, `/playlist/` | Spotify oEmbed API (no auth needed): track/album name, artist, cover art. Full playlist track listing with auth. | `httpx`, Spotify API |
| **Generic URL** | Everything else | `readability-lxml` for article content, full metadata extraction (OG tags, JSON-LD, schema.org), full-page archive. | `httpx`, `readability-lxml`, `monolith` |
| **Image** | Upload / paste (JPEG, PNG, WebP, GIF) | OCR via `pytesseract` or `EasyOCR`, EXIF extraction, AI visual description. | `pytesseract`, `Pillow` |
| **PDF** | Upload (`.pdf`) | Full-text extraction, metadata, page count, summary. | `PyMuPDF` |

**Extraction Pipeline (per item):**
1. **Route** — match URL to processor
2. **Fetch metadata** — title, author, timestamps, platform-specific data
3. **Extract content** — readable text, captions, transcripts, comments
4. **Download media** — images, thumbnails, optionally video/audio (configurable per user)
5. **AI enrich** — auto-tag, auto-summarize, generate embeddings, detect connections
6. **Index** — push to Meilisearch (full-text) + vector DB (semantic)
7. **Connect** — find related items in the user's knowledge base, suggest connections

#### 4.1.3 AI-Powered Smart Organization & Knowledge Intelligence

This is the brain of 4DPocket — what transforms it from a link saver into a **knowledge base that thinks**.

**Local-First AI (Default):**
- **Ollama Integration**: Auto-tag and auto-summarize using local LLMs (Llama 3, Mistral, Phi-3)
- **Sentence Transformers**: Local embedding generation for semantic search (`all-MiniLM-L6-v2`)

**External API Support (Optional):**
- OpenAI API (GPT-4o) for tagging/summarization
- Anthropic API (Claude) for tagging/summarization
- Google Gemini API as alternative
- Configurable: user chooses local vs API per feature

---

##### Smart Tags System

Tags in 4DPocket are not dumb labels — they're an **intelligent taxonomy** that evolves with your knowledge base.

**Tag Intelligence Layers:**

| Layer | What It Does | Example |
|---|---|---|
| **Auto-Tagging** | AI reads extracted content and assigns relevant tags | Save a Python tutorial → auto-tagged `python`, `programming`, `tutorial` |
| **Hierarchical Tags** | Tags have parent-child relationships, auto-inferred | `python` auto-nests under `programming/python` |
| **Tag Relationships** | AI learns which tags co-occur and suggests related tags | When you tag `react`, it suggests `frontend`, `javascript` |
| **Tag Evolution** | As your library grows, AI suggests merging/splitting tags | "You have 5 items tagged `ml` and 12 tagged `machine-learning` — merge?" |
| **Smart Tag Rules** | Tags can have auto-apply rules | "Anything from `arxiv.org` → auto-tag `research-paper`" |
| **Tag Strength** | Each tag has a confidence score (0-1) from AI | Strong: `python` (0.95), Weak: `data-science` (0.4) — user can filter by confidence |
| **Trending Tags** | Dashboard shows which topics you're saving most this week/month | "You've been deep in `rust` and `systems-programming` this week" |
| **Tag Descriptions** | AI generates a one-line description for each tag based on your usage | `distributed-systems`: "Articles and videos about scaling, consensus, and microservices" |

**How Smart Tags Work on Save:**
```
User saves: "Building a RAG Pipeline with LangChain and Pinecone"
                    │
                    ▼
         ┌──────────────────┐
         │  AI Tag Analysis   │
         │                    │
         │  1. Content scan   │  → reads title, extracted text, metadata
         │  2. Entity extract │  → LangChain, Pinecone, RAG
         │  3. Topic classify │  → AI/ML, Python, Vector DBs
         │  4. Match existing │  → checks your existing tags
         │  5. Hierarchy fit  │  → ai/llm/rag, programming/python
         └────────┬───────────┘
                  │
                  ▼
         Generated tags:
         ├── ai/llm/rag (0.97)         ← high confidence, auto-applied
         ├── programming/python (0.89)  ← high confidence, auto-applied
         ├── vector-databases (0.82)    ← high confidence, auto-applied
         ├── tutorial (0.71)            ← medium, auto-applied (above threshold)
         └── langchain (0.65)           ← suggested, user confirms
```

**User Tag Preferences:**
- Set auto-apply threshold (default: 0.7) — tags above this are applied automatically
- Set suggestion threshold (default: 0.4) — tags above this are shown as suggestions
- Pin favorite tags for quick manual tagging
- Blocklist tags you never want suggested

---

##### Related Content — "Your Knowledge, Connected"

The most powerful feature of 4DPocket as a knowledge base: **every item knows what else in your pocket is related to it**.

**When You Save Something New:**

The moment you save a new item, 4DPocket immediately shows you:

```
┌─────────────────────────────────────────────────────┐
│  ✓ Saved: "Building RAG Pipelines with LangChain"   │
│                                                      │
│  📎 Related in your knowledge base:                  │
│                                                      │
│  ┌─ Strong match (semantic) ─────────────────────┐  │
│  │ "Vector Databases Explained" (saved 2 weeks ago)│  │
│  │ "LangChain vs LlamaIndex" (saved 3 days ago)   │  │
│  └─────────────────────────────────────────────────┘  │
│                                                      │
│  ┌─ Same topic ──────────────────────────────────┐  │
│  │ "OpenAI Embeddings Guide" (tagged: ai/llm)    │  │
│  │ "Pinecone Getting Started" (tagged: vector-db) │  │
│  └─────────────────────────────────────────────────┘  │
│                                                      │
│  ┌─ Same author/source ──────────────────────────┐  │
│  │ "LangChain Agents Deep Dive" (same blog)      │  │
│  └─────────────────────────────────────────────────┘  │
│                                                      │
│  💡 Suggestion: Add to collection "AI/ML Learning"?  │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**How Related Content Works:**

| Signal | How It's Used | Weight |
|---|---|---|
| **Semantic similarity** | Embedding cosine distance between items | Highest — finds conceptually related items even if no shared tags |
| **Shared tags** | Items with overlapping tags | High — especially for high-confidence AI tags |
| **Same source/author** | Same domain, same YouTube channel, same Reddit user, same GitHub org | Medium — groups content by creator |
| **Same platform** | Both from YouTube, both from Reddit, etc. | Low — only as tiebreaker |
| **Temporal proximity** | Saved around the same time | Low — you were likely researching the same topic |
| **Co-occurrence in collections** | If other users put A and B in the same collection | Medium — collaborative signal |
| **Link graph** | Item A links to Item B (or vice versa) | High — explicit content relationship |

**Related Content Surfaces:**

| Where | What Shows |
|---|---|
| **On save** | Instant "related items" panel when you add something new |
| **Item detail page** | "Related in your library" sidebar |
| **Search results** | "See also" suggestions alongside search hits |
| **Dashboard** | "Connections you might have missed" — items saved weeks apart that are semantically related |
| **Collection suggestions** | "These 5 items could form a collection about X" |

---

##### Knowledge Intelligence Features (Full List)

| Feature | Description |
|---|---|
| **Auto-Tagging** | AI analyzes content and assigns relevant tags with confidence scores |
| **Smart Tag Hierarchy** | Tags auto-organize into parent-child trees based on your usage |
| **Tag Evolution** | AI suggests merging near-duplicate tags, splitting overloaded tags |
| **Auto-Summarization** | Generates 2-3 sentence summary for every saved item |
| **Related Items (on save)** | Immediately surface related content from your knowledge base when you save |
| **Related Items (browsing)** | "Similar to this" panel on every item detail page |
| **Smart Collections** | AI suggests groupings ("Your ML papers", "Design inspiration") |
| **Collection Auto-Suggest** | "This item fits in your 'React Patterns' collection" |
| **Duplicate Detection** | Detects near-duplicate content before saving (same URL, similar content) |
| **Knowledge Gaps** | "You have 20 items about React but nothing about testing — here's a suggestion" |
| **Trending Topics** | Dashboard shows what topics you're saving most, how your interests evolve |
| **Stale Knowledge** | Flags items that may be outdated (old API docs, deprecated libraries) |
| **Cross-Platform Connections** | Links a YouTube video to the blog post it references, or a Reddit discussion to the article it's about |

#### 4.1.4 Search — The Heart of 4DPocket

**Meilisearch-Powered Full-Text Search:**
- Sub-50ms search responses
- Typo tolerance (finds "javscript" when you meant "javascript")
- Faceted filtering (by type, tag, date, source)
- Highlighted search results
- Search-as-you-type with instant results

**Semantic Search (Local Embeddings):**
- Vector similarity search using sentence-transformers
- "Find me that article about React performance" → finds it even if those exact words aren't in the title
- ChromaDB or Qdrant for local vector storage

**Search Filters:**
```
type:youtube tag:machine-learning after:2024-01
source:github stars:>1000
has:transcript lang:python
```

#### 4.1.5 Organization

- **Tags**: AI-generated + manual. Hierarchical tag support (e.g., `programming/python/fastapi`)
- **Lists / Collections**: Manual groupings (like playlists). Shareable.
- **Favorites**: Quick-access starred items
- **Archive**: Hide without deleting
- **Smart Filters**: Saved search queries that auto-update
- **Timeline View**: Chronological feed of everything saved

#### 4.1.6 PWA Web Application

**Tech Stack:**
- Frontend: React + TypeScript + Vite (compiled to static PWA)
- Styling: Tailwind CSS + shadcn/ui components
- State: TanStack Query for server state, Zustand for client state
- PWA: Service worker for offline, install prompt, push notifications

**Responsive Design:**
```
┌──────────────────────────────────────────────┐
│  Desktop (>1024px)                            │
│  ┌──────────┬───────────────────────────────┐ │
│  │ Sidebar  │  Content Grid (3-4 columns)   │ │
│  │ Nav +    │  Card-based layout             │ │
│  │ Tags     │  with preview                  │ │
│  └──────────┴───────────────────────────────┘ │
├──────────────────────────────────────────────┤
│  Tablet (768-1024px)                          │
│  ┌──────────────────────────────────────────┐ │
│  │  Collapsible sidebar + 2-column grid     │ │
│  └──────────────────────────────────────────┘ │
├──────────────────────────────────────────────┤
│  Mobile (<768px)                              │
│  ┌──────────────────────────────────────────┐ │
│  │  Bottom nav + single column list/cards   │ │
│  │  Pull-to-refresh, swipe actions          │ │
│  └──────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

**Key UI Patterns:**
- **Command Palette** (Cmd+K): Search anything, quick actions, navigation
- **Card Previews**: Rich preview cards with thumbnail, title, tags, summary
- **Drag & Drop**: Reorder items, add to lists
- **Dark/Light Mode**: System-aware with manual toggle
- **Keyboard Shortcuts**: Vim-inspired navigation for power users

---

### 4.2 Extended Features (Phase 2)

#### 4.2.1 Browser Extension
- Chrome & Firefox extension
- Right-click "Save to 4DPocket"
- Highlight text on page → save as note with source URL
- Auto-detect and save current page
- **Highlight Capture**: Select text on any page → save highlight with context, page URL, and position
- Sidebar panel for quick view of highlights from current page

#### 4.2.2 Highlights & Annotations System
- **Highlight Storage**: Save highlighted text from any bookmarked page with source context
- **Annotation Notes**: Attach notes to specific highlights
- **Highlights Page**: Dedicated page to browse all highlights across all bookmarks
- **Search Highlights**: Full-text search within highlights
- **Highlight Colors**: Color-code highlights by category (important, question, idea, etc.)
- **Export Highlights**: Export all highlights from a bookmark as Markdown or PDF
- *Better than Karakeep*: Karakeep has basic highlights — we add color coding, annotations, dedicated search, and export

#### 4.2.3 RSS Feed Ingestion
- **Subscribe to RSS/Atom feeds** → auto-save new items to 4DPocket
- **Feed Categories as Tags**: RSS feed categories automatically become tags
- **Feed-to-List Mapping**: Route feed items to specific lists
- **Configurable Polling**: Per-feed polling interval (15min, 1hr, 6hr, daily)
- **YouTube Channel Feeds**: Subscribe to YT channels as RSS → auto-process with YouTube processor
- **Reddit Subreddit Feeds**: Subscribe to subreddit feeds → auto-process with Reddit processor
- **Feed Dashboard**: Monitor feed health, last fetch time, item count
- *Better than Karakeep*: Karakeep does hourly polling — we do configurable intervals + smart content-type routing

#### 4.2.4 Import / Export & Backup
- **Import from**: Chrome bookmarks, Pocket, Karakeep, Linkwarden, Omnivore, Raindrop.io, Pinboard, Tab Session Manager
- **Export to**: JSON, CSV, HTML bookmarks, Markdown, PDF report
- **Scheduled Backups**: Cron-based automatic backups (SQLite DB + files + Meilisearch dump)
- **Backup Destinations**: Local disk, S3-compatible, WebDAV
- **Browser Bookmark Sync**: Two-way sync via Floccus integration
- *Better than Karakeep*: We add PDF export, S3/WebDAV backup destinations, and two-way Floccus sync

#### 4.2.5 Knowledge Base & Multi-User Architecture

4DPocket is fundamentally a **per-user knowledge base**, not a shared database with permissions bolted on. Each user has their own pocket — their own library of knowledge — and sharing is an explicit, intentional act.

**Per-User Knowledge Base:**
- Every user gets an isolated knowledge base (their "pocket")
- Items, tags, lists, notes, AI enrichments, and embeddings are scoped to the user
- Each user's AI learns *their* tagging patterns and interests over time
- Personal dashboard, personal search, personal stats — your pocket is *yours*

**Selective Sharing Model:**
```
┌─────────────────────┐         ┌─────────────────────┐
│   User A's Pocket    │         │   User B's Pocket    │
│                      │         │                      │
│  ┌───────────────┐  │  share  │  ┌───────────────┐  │
│  │ ML Collection  │──┼────────▶│  │ Shared with me │  │
│  └───────────────┘  │         │  └───────────────┘  │
│  ┌───────────────┐  │         │  ┌───────────────┐  │
│  │ Private Notes  │  │         │  │ Recipe Saves   │──┼──▶ (shared back)
│  └───────────────┘  │         │  └───────────────┘  │
│  ┌───────────────┐  │         │                      │
│  │ Single Item   │──┼─────────▶  (appears in B's    │
│  └───────────────┘  │         │   "Shared with me")  │
└─────────────────────┘         └─────────────────────┘
```

**Sharing Granularity:**
| What | How | Visibility |
|---|---|---|
| **Single item** | Share button → generate link or share to specific user | Recipient sees item in "Shared with me" |
| **Collection/List** | Share entire list as read-only or editable | Recipient gets a live-updating mirror |
| **Tag/Topic** | Share all items with tag "recipes" with a user | New items auto-shared as you tag them |
| **Public link** | Generate public URL (no login needed) | Anyone with link can view (optionally time-limited) |
| **Knowledge feed** | Subscribe to another user's public items | Like following — their public saves appear in your feed |

**Collaboration Features:**
- **Shared Lists**: Invite users as viewer or editor (role-based). Both users can add items.
- **Shared Tags**: When sharing a collection, tag taxonomy travels with it
- **Comments on shared items**: "Hey, check out the third section of this article"
- **RSS Feed Generation**: Every list/collection auto-generates an RSS feed URL for external consumption
- **Share history**: See what you've shared with whom, revoke anytime

**Multi-User Roles (instance-level):**
| Role | Permissions |
|---|---|
| **Admin** | Full instance management, user creation, global settings |
| **User** | Full knowledge base, sharing, all features |
| **Guest** | View shared items only, no own pocket (for share link recipients who create accounts) |

- *Better than Karakeep*: Karakeep has basic multi-user + collaborative lists. We have per-user knowledge bases with granular selective sharing, knowledge feeds, tag-based auto-sharing, and public links with expiry.

#### 4.2.6 Automation / Rules Engine
- **Condition-Action Rules**: "If saved from reddit.com → auto-tag 'reddit' + add to 'Reddit Saves' list"
- **Time-Based Rules**: "If tagged 'read-later' and older than 30 days → move to 'Stale' list"
- **AI-Powered Rules**: "If content is about machine learning → add to 'ML' list" (uses AI classification)
- **Webhook Triggers**: Fire webhooks on save/tag/delete/archive events
- **Incoming Webhooks**: Accept bookmarks from external services (Zapier, n8n, IFTTT)
- **Rule Templates**: Pre-built rules for common patterns
- *Better than Karakeep*: We add AI-powered conditions, incoming webhooks, and rule templates

#### 4.2.7 Read-it-Later Mode
- Distraction-free reader view (extracted article content via readability)
- Text-to-speech playback (local TTS or browser API)
- Reading progress tracking (resume where you left off)
- Highlights and inline annotations
- Estimated reading time
- Reading queue with priority ordering

#### 4.2.8 Bulk Actions
- Select multiple items → bulk tag, bulk move to list, bulk archive, bulk delete
- Bulk re-process AI (re-tag, re-summarize selected items)
- Bulk export selected items
- Select all / select by filter

#### 4.2.9 Multi-Language Support (i18n)
- UI translated into multiple languages
- Community translation support (Weblate or Crowdin)
- Auto-detect user browser language

#### 4.2.11 Video Archival
- Archive YouTube videos locally via `yt-dlp` (configurable quality)
- Store video thumbnails and metadata
- Transcript indexing for search
- Playback from local archive if original is deleted

---

### 4.3 Future Platforms (Phase 3)

- **macOS Menubar App**: Python + `rumps` or Swift wrapper. Quick capture from any app.
- **Android App**: React Native or Kotlin
- **iOS App**: React Native or Swift
- **CLI Tool**: `4dp save <url>`, `4dp search <query>`, `4dp list`

---

## 5. System Architecture

### 5.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        4DPocket System                            │
│                     "Your Magic Library"                          │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐       │
│  │   PWA App    │  │  Browser Ext  │  │   CLI / API       │       │
│  │  (React+TS)  │  │  (Chrome/FF)  │  │  Clients          │       │
│  └──────┬───────┘  └──────┬───────┘  └────────┬──────────┘       │
│         │                  │                    │                  │
│         └──────────────────┼────────────────────┘                  │
│                            │                                       │
│                   ┌────────▼────────┐                             │
│                   │   FastAPI        │                             │
│                   │   REST API       │                             │
│                   │   + WebSocket    │                             │
│                   └────────┬────────┘                             │
│                            │                                       │
│    ┌───────────┬───────────┼───────────┬──────────────┐          │
│    │           │           │           │              │          │
│  ┌─▼────────┐┌─▼────────┐┌─▼────────┐┌─▼──────────┐┌─▼───────┐ │
│  │ Platform  ││ AI &     ││ Search   ││ Knowledge  ││Background│ │
│  │ Processor ││ Smart    ││ Engine   ││ Sharing    ││ Workers  │ │
│  │ Registry  ││ Tags     ││          ││ Engine     ││          │ │
│  │ (15+      ││(Ollama/  ││(Meili-   ││(per-user   ││ (ARQ/    │ │
│  │ platforms)││ OpenAI/  ││ search + ││ pockets +  ││  Huey)   │ │
│  │           ││ local)   ││ vector)  ││ selective  ││          │ │
│  │           ││          ││          ││ sharing)   ││          │ │
│  └─────┬─────┘└────┬─────┘└────┬─────┘└─────┬─────┘└────┬─────┘ │
│        │           │           │             │           │       │
│        └───────────┴───────┬───┴─────────────┴───────────┘       │
│                            │                                       │
│                   ┌────────▼────────┐                             │
│                   │   Data Layer     │                             │
│                   │  (user-scoped)   │                             │
│                   │                  │                             │
│                   │  SQLite/Postgres │                             │
│                   │  Meilisearch     │                             │
│                   │  ChromaDB/Qdrant │                             │
│                   │  File Storage    │                             │
│                   └─────────────────┘                             │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Backend Architecture (Python)

```
4dpocket/
├── pyproject.toml                 # Project metadata, dependencies (uv/poetry)
├── alembic.ini                    # Database migrations config
├── Dockerfile                     # Multi-stage Python build
├── docker-compose.yml             # Full stack orchestration
├── Makefile                       # Dev convenience commands
│
├── src/
│   └── fourdpocket/               # Main Python package
│       ├── __init__.py
│       ├── main.py                # FastAPI app entry point
│       ├── config.py              # Settings via pydantic-settings
│       │
│       ├── api/                   # API layer
│       │   ├── __init__.py
│       │   ├── router.py          # Root router
│       │   ├── deps.py            # Dependency injection
│       │   ├── middleware.py      # CORS, auth, rate limiting
│       │   ├── items.py           # KnowledgeItem CRUD endpoints
│       │   ├── notes.py           # Notes endpoints
│       │   ├── search.py          # Search endpoints
│       │   ├── tags.py            # Tag management
│       │   ├── collections.py     # Collection endpoints
│       │   ├── sharing.py         # Share, unshare, public links, feeds
│       │   ├── import_export.py   # Import/export endpoints
│       │   ├── ai.py              # AI feature endpoints
│       │   └── auth.py            # Auth endpoints (JWT)
│       │
│       ├── models/                # SQLAlchemy / SQLModel models
│       │   ├── __init__.py
│       │   ├── item.py            # KnowledgeItem model
│       │   ├── note.py            # Note model (standalone + attached)
│       │   ├── tag.py             # Tag model (user-scoped)
│       │   ├── collection.py      # Collection model
│       │   ├── user.py            # User model (with role enum)
│       │   ├── share.py           # Share + ShareRecipient models
│       │   ├── feed.py            # KnowledgeFeed model
│       │   ├── comment.py         # Comment model (on shared items)
│       │   ├── rule.py            # Automation rule model
│       │   └── embedding.py       # Embedding model
│       │
│       ├── processors/            # Content type processors (plugin-based)
│       │   ├── __init__.py
│       │   ├── base.py            # BaseProcessor interface + registry
│       │   ├── registry.py        # Processor discovery & URL pattern matching
│       │   ├── pipeline.py        # Extraction pipeline orchestrator
│       │   ├── generic_url.py     # Generic URL processor (fallback)
│       │   ├── youtube.py         # YouTube video/shorts processor
│       │   ├── instagram.py       # Instagram post/reel/story processor
│       │   ├── reddit.py          # Reddit post/comment processor
│       │   ├── twitter.py         # Twitter/X post/thread processor
│       │   ├── threads.py         # Threads.net processor
│       │   ├── tiktok.py          # TikTok video processor
│       │   ├── github.py          # GitHub repo/issue/PR/gist processor
│       │   ├── hackernews.py      # Hacker News processor
│       │   ├── stackoverflow.py   # Stack Overflow Q&A processor
│       │   ├── mastodon.py        # Mastodon/Fediverse processor
│       │   ├── substack.py        # Substack article processor
│       │   ├── medium.py          # Medium article processor
│       │   ├── linkedin.py        # LinkedIn post processor
│       │   ├── spotify.py         # Spotify track/album/playlist processor
│       │   ├── image.py           # Image processor (OCR)
│       │   └── pdf.py             # PDF processor
│       │
│       ├── ai/                    # AI engine
│       │   ├── __init__.py
│       │   ├── base.py            # AI provider interface
│       │   ├── ollama.py          # Ollama local LLM
│       │   ├── openai.py          # OpenAI API
│       │   ├── anthropic.py       # Anthropic API
│       │   ├── tagger.py          # Auto-tagging logic
│       │   ├── summarizer.py      # Auto-summarization
│       │   ├── connector.py       # Related items / knowledge graph connections
│       │   └── embeddings.py      # Embedding generation
│       │
│       ├── search/                # Search engine
│       │   ├── __init__.py
│       │   ├── meilisearch.py     # Meilisearch client (user-scoped indexes)
│       │   ├── semantic.py        # Vector/semantic search
│       │   └── indexer.py         # Index management
│       │
│       ├── sharing/               # Knowledge sharing engine
│       │   ├── __init__.py
│       │   ├── share_manager.py   # Create/revoke shares, manage recipients
│       │   ├── feed_manager.py    # Knowledge feed subscriptions
│       │   └── permissions.py     # Share permission checks
│       │
│       ├── workers/               # Background task workers
│       │   ├── __init__.py
│       │   ├── fetcher.py         # URL metadata fetcher
│       │   ├── archiver.py        # Page archival worker
│       │   ├── screenshot.py      # Screenshot capture
│       │   ├── media_downloader.py # Platform media download worker
│       │   ├── ai_enrichment.py   # AI tagging/summary/connection worker
│       │   └── scheduler.py       # Periodic tasks (feeds, backups)
│       │
│       ├── storage/               # File storage (user-scoped paths)
│       │   ├── __init__.py
│       │   ├── local.py           # Local filesystem storage
│       │   └── s3.py              # S3-compatible storage (optional)
│       │
│       └── db/                    # Database layer
│           ├── __init__.py
│           ├── session.py         # DB session management
│           └── migrations/        # Alembic migrations
│
├── frontend/                      # PWA Frontend
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── public/
│   │   ├── manifest.json          # PWA manifest
│   │   ├── sw.js                  # Service worker
│   │   └── icons/                 # App icons (all sizes)
│   │
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/                   # API client (openapi-fetch)
│       ├── components/
│       │   ├── ui/                # shadcn/ui primitives
│       │   ├── layout/            # Shell, Sidebar, BottomNav
│       │   ├── bookmark/          # BookmarkCard, BookmarkForm
│       │   ├── search/            # SearchBar, SearchResults, Filters
│       │   ├── editor/            # MarkdownEditor, NoteForm
│       │   └── common/            # CommandPalette, ThemeToggle
│       ├── pages/
│       │   ├── Dashboard.tsx        # Recent items, stats, activity feed
│       │   ├── Search.tsx           # Full-text + semantic search
│       │   ├── KnowledgeBase.tsx    # Main library view (grid/list, filters)
│       │   ├── Collections.tsx      # User collections
│       │   ├── Tags.tsx             # Tag management + tag cloud
│       │   ├── SharedWithMe.tsx     # Items/collections shared by others
│       │   ├── Feed.tsx             # Knowledge feed from followed users
│       │   ├── Settings.tsx         # User settings, AI prefs, sharing defaults
│       │   ├── ItemDetail.tsx       # Full item view with extracted content
│       │   └── PublicShare.tsx      # Public link view (no auth)
│       ├── hooks/                 # Custom React hooks
│       ├── stores/                # Zustand stores
│       ├── lib/                   # Utilities
│       └── styles/                # Global styles
│
├── tests/                         # Test suite
│   ├── conftest.py
│   ├── test_api/
│   ├── test_processors/
│   ├── test_ai/
│   ├── test_search/
│   └── test_workers/
│
├── scripts/                       # Utility scripts
│   ├── seed.py                    # Seed demo data
│   └── migrate.py                 # Run migrations
│
└── docs/                          # Documentation
    ├── api.md
    ├── deployment.md
    └── configuration.md
```

### 5.3 Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **API Framework** | FastAPI | Async, fast, auto-docs (OpenAPI), Python-native |
| **ORM** | SQLModel (SQLAlchemy + Pydantic) | Type-safe, FastAPI-native, migration support |
| **Database** | SQLite (default) / PostgreSQL (optional) | Zero-config local, upgrade path for multi-user |
| **Migrations** | Alembic | Industry standard for SQLAlchemy |
| **Search** | Meilisearch | Sub-50ms, typo-tolerant, faceted, battle-tested |
| **Vector DB** | ChromaDB (default) / Qdrant (optional) | Local embeddings storage for semantic search |
| **Background Jobs** | ARQ (async Redis queue) or Huey (SQLite) | Lightweight. Huey for zero-dep local, ARQ for Docker |
| **AI - Local** | Ollama | Run LLMs locally, wide model support |
| **AI - Embeddings** | sentence-transformers | Local embedding generation, no API needed |
| **AI - External** | OpenAI / Anthropic / Gemini SDKs | Optional cloud AI for better quality |
| **Web Scraping** | httpx + readability-lxml | Async HTTP + article extraction |
| **Page Archival** | monolith (Rust binary) | Single-file complete page archival |
| **Screenshots** | Playwright | Headless browser screenshots + JS-rendered scraping |
| **YouTube** | yt-dlp + youtube-transcript-api | Metadata + transcript + optional video download |
| **Instagram** | instaloader | Public post/reel extraction, session cookie auth for private |
| **TikTok** | yt-dlp (TikTok support) | Video metadata + optional download |
| **Twitter/X** | gallery-dl + httpx (Nitter/FixTweet) | Tweet/thread extraction without official API |
| **Reddit** | httpx (JSON API — no key needed) | Posts + comments via `.json` URL trick |
| **Mastodon** | httpx (Mastodon API) | Toot extraction, auto-instance detection |
| **OCR** | pytesseract / EasyOCR | Image text extraction |
| **PDF** | PyMuPDF (fitz) | Fast PDF text extraction |
| **Auth** | JWT (python-jose) + passlib | Stateless auth, bcrypt passwords |
| **Config** | pydantic-settings | Type-safe config from env vars |
| **Frontend** | React + TypeScript + Vite | Fast, modern, excellent PWA support |
| **UI Components** | shadcn/ui + Tailwind CSS | Beautiful, accessible, customizable |
| **Frontend State** | TanStack Query + Zustand | Server cache + client state |
| **PWA** | vite-plugin-pwa (Workbox) | Service worker, offline, installable |
| **Package Manager** | uv (Python) + pnpm (JS) | Fast, modern package management |
| **Testing** | pytest + pytest-asyncio | Async test support |

### 5.4 Data Model

The data model is **user-scoped** — every knowledge item belongs to exactly one user's pocket. Sharing creates **references**, not copies, so shared items stay in sync.

```
┌──────────────────┐
│      User         │
├──────────────────┤
│ id (uuid)        │
│ email            │
│ password_hash    │
│ display_name     │
│ avatar_url       │
│ role (enum)      │  ← admin | user | guest
│ settings (json)  │  ← per-user AI prefs, media download prefs, theme
│ created_at       │
└────────┬─────────┘
         │ owns
         ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  KnowledgeItem    │     │      Tag          │     │    Collection     │
├──────────────────┤     ├──────────────────┤     ├──────────────────┤
│ id (uuid)        │     │ id (uuid)        │     │ id (uuid)        │
│ user_id (fk)     │  ┌─▶│ user_id (fk)     │     │ user_id (fk)     │
│ item_type (enum) │  │  │ name             │     │ name             │
│  → url           │  │  │ slug             │     │ description      │
│  → note          │  │  │ parent_id (fk)   │     │ icon             │
│  → image         │  │  │ ai_generated     │     │ is_public        │
│  → pdf           │  │  │ color            │     │ is_smart         │
│  → code_snippet  │  │  │ usage_count      │     │ smart_query      │
│ source_platform  │  │  └──────────────────┘     │ share_mode       │  ← private | link | invite
│  → youtube       │  │                            │ created_at       │
│  → instagram     │  │  ┌──────────────────┐     └──────────────────┘
│  → reddit        │  │  │   item_tag        │
│  → twitter       │  │  ├──────────────────┤     ┌──────────────────┐
│  → threads       │  ├──│ item_id (fk)     │     │ collection_item   │
│  → tiktok        │  │  │ tag_id (fk)      │     ├──────────────────┤
│  → github        │  │  └──────────────────┘     │ collection_id    │
│  → hackernews    │  │                            │ item_id (fk)     │
│  → stackoverflow │  │                            │ position (int)   │
│  → mastodon      │  │                            │ added_at         │
│  → substack      │  │                            └──────────────────┘
│  → medium        │  │
│  → linkedin      │  │
│  → spotify       │  │
│  → generic       │  │
│ url              │  │
│ title            │  │
│ description      │  │
│ content (text)   │  │  ← extracted readable content
│ raw_content      │  │  ← original HTML / JSON
│ summary (AI)     │  │
│ screenshot_path  │  │
│ archive_path     │  │
│ media (json)     │  │  ← array of downloaded images/videos/audio
│ metadata (json)  │  │  ← platform-specific: duration, score, hashtags, etc.
│ is_favorite      │  │
│ is_archived      │  │
│ reading_progress │  │  ← 0-100% for read-it-later
│ created_at       │  │
│ updated_at       │  │
└──────────────────┘  │
                      │
┌──────────────────┐  │  ┌──────────────────┐
│      Note         │  │  │    Embedding      │
├──────────────────┤  │  ├──────────────────┤
│ id (uuid)        │  │  │ item_id (uuid)   │
│ user_id (fk)     │  │  │ item_type        │  ← knowledge_item | note
│ item_id (fk)     │  │  │ vector (blob)    │
│  ← nullable;     │  │  │ model            │
│    standalone or  │  │  └──────────────────┘
│    attached to    │  │
│    a KnowledgeItem│  │
│ content (md)     │  │  ┌──────────────────┐
│ title            │  │  │      Rule         │
│ summary (AI)     │  │  ├──────────────────┤
│ created_at       │  │  │ id (uuid)        │
│ updated_at       │  │  │ user_id (fk)     │
└──────────────────┘  │  │ name             │
                      │  │ condition (json)  │
         (tags link to│  │ action (json)     │
          items and   │  │ is_active         │
          notes) ─────┘  └──────────────────┘


SHARING & COLLABORATION TABLES:

┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│    Share          │     │  ShareRecipient   │     │  KnowledgeFeed   │
├──────────────────┤     ├──────────────────┤     ├──────────────────┤
│ id (uuid)        │     │ id (uuid)        │     │ id (uuid)        │
│ owner_id (fk)    │     │ share_id (fk)    │     │ subscriber_id    │  ← user following
│ share_type       │     │ user_id (fk)     │     │ publisher_id     │  ← user being followed
│  → item          │     │ role (enum)      │     │ filter (json)    │  ← optional: only certain tags
│  → collection    │     │  → viewer        │     │ created_at       │
│  → tag           │     │  → editor        │     └──────────────────┘
│ item_id (fk)     │     │ accepted (bool)  │
│ collection_id    │     │ created_at       │     ┌──────────────────┐
│ tag_id           │     └──────────────────┘     │   Comment         │
│ public_token     │  ← for public links          ├──────────────────┤
│ expires_at       │  ← optional expiry            │ id (uuid)        │
│ created_at       │                               │ user_id (fk)     │
└──────────────────┘                               │ item_id (fk)     │
                                                   │ content (text)   │
                                                   │ created_at       │
                                                   └──────────────────┘
```

### 5.5 API Design

**Base URL:** `/api/v1`

All item/tag/collection endpoints are **user-scoped** — a user only sees their own data unless accessing shared content.

**Knowledge Items (core CRUD):**

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/items` | Create knowledge item (auto-detects platform & content type) |
| `GET` | `/items` | List items (paginated, filtered by type/platform/tag/date) |
| `GET` | `/items/:id` | Get item details (includes extracted content, metadata, media) |
| `PATCH` | `/items/:id` | Update item (title, tags, notes, etc.) |
| `DELETE` | `/items/:id` | Delete item |
| `POST` | `/items/:id/archive` | Trigger full-page archival |
| `POST` | `/items/:id/enrich` | Re-run AI enrichment (re-tag, re-summarize, re-connect) |
| `POST` | `/items/:id/reprocess` | Re-run platform processor (re-fetch content) |
| `GET` | `/items/:id/related` | Get AI-suggested related items from your knowledge base |
| `POST` | `/items/bulk` | Bulk action (tag, move, archive, delete, re-enrich) |

**Notes:**

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/notes` | Create standalone note (markdown) |
| `GET` | `/notes` | List notes |
| `PATCH` | `/notes/:id` | Update note |
| `DELETE` | `/notes/:id` | Delete note |
| `POST` | `/items/:id/notes` | Attach note to a knowledge item |
| `GET` | `/items/:id/notes` | List notes attached to an item |

**Search:**

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/search` | Full-text search (Meilisearch) across your knowledge base |
| `GET` | `/search/semantic` | Semantic/vector search ("find that article about...") |
| `GET` | `/search/filters` | Available filter facets (types, platforms, tags, date ranges) |

**Tags:**

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/tags` | List all your tags (with usage counts) |
| `POST` | `/tags` | Create tag |
| `PATCH` | `/tags/:id` | Update tag (rename, recolor, reparent) |
| `DELETE` | `/tags/:id` | Delete tag (optionally untag all items) |
| `GET` | `/tags/:id/items` | List all items with this tag |

**Collections:**

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/collections` | List all your collections |
| `POST` | `/collections` | Create collection |
| `PATCH` | `/collections/:id` | Update collection |
| `DELETE` | `/collections/:id` | Delete collection |
| `POST` | `/collections/:id/items` | Add items to collection |
| `DELETE` | `/collections/:id/items/:item_id` | Remove item from collection |
| `PUT` | `/collections/:id/items/reorder` | Reorder items in collection |

**Sharing & Collaboration:**

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/shares` | Create a share (item, collection, or tag-based) |
| `GET` | `/shares` | List your outgoing shares |
| `DELETE` | `/shares/:id` | Revoke a share |
| `POST` | `/shares/:id/recipients` | Add recipient to share |
| `DELETE` | `/shares/:id/recipients/:user_id` | Remove recipient |
| `GET` | `/shared-with-me` | List items/collections shared with you |
| `POST` | `/shares/:id/accept` | Accept a share invitation |
| `GET` | `/public/:token` | Access a public shared link (no auth) |
| `POST` | `/feeds/subscribe/:user_id` | Subscribe to a user's public knowledge feed |
| `DELETE` | `/feeds/unsubscribe/:user_id` | Unsubscribe from feed |
| `GET` | `/feeds` | Get your feed (items from users you follow) |
| `POST` | `/items/:id/comments` | Comment on a shared item |
| `GET` | `/items/:id/comments` | List comments on an item |

**Import / Export:**

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/import/:source` | Import from external source (Chrome, Pocket, Karakeep, etc.) |
| `GET` | `/export/:format` | Export data (JSON, CSV, Markdown, HTML, PDF) |

**Auth & User:**

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register user |
| `POST` | `/auth/login` | Login (returns JWT) |
| `GET` | `/auth/me` | Current user profile |
| `GET` | `/settings` | Get user settings (AI prefs, media prefs, sharing defaults) |
| `PATCH` | `/settings` | Update settings |
| `GET` | `/stats` | Dashboard statistics (items by platform, tags, activity) |
| `GET` | `/users/:id/public` | Public profile (display name, public collections) |

---

## 6. Deployment Architecture

### 6.1 Native Python (Development / Single User)

```bash
# Install
uv pip install 4dpocket

# Run (uses SQLite + embedded Meilisearch)
4dpocket serve

# Opens at http://localhost:4040
# Data stored in ~/.4dpocket/
```

**Directory structure:**
```
~/.4dpocket/
├── config.toml         # User configuration
├── data.db             # SQLite database
├── chroma/             # ChromaDB vector store
├── archives/           # Archived pages
├── screenshots/        # Page screenshots
├── uploads/            # User uploaded files
└── logs/               # Application logs
```

### 6.2 Docker Compose (Self-Hosted / Multi-User)

```yaml
# docker-compose.yml
version: "3.8"

services:
  app:
    image: 4dpocket/4dpocket:latest
    build: .
    ports:
      - "4040:4040"
    environment:
      - DATABASE_URL=postgresql://4dp:4dp@db:5432/4dpocket
      - MEILI_URL=http://meilisearch:7700
      - MEILI_MASTER_KEY=${MEILI_MASTER_KEY}
      - OLLAMA_URL=http://ollama:11434
      - SECRET_KEY=${SECRET_KEY}
      - STORAGE_PATH=/data
    volumes:
      - 4dp-data:/data
    depends_on:
      - db
      - meilisearch

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=4dp
      - POSTGRES_PASSWORD=4dp
      - POSTGRES_DB=4dpocket
    volumes:
      - 4dp-postgres:/var/lib/postgresql/data

  meilisearch:
    image: getmeili/meilisearch:v1.12
    environment:
      - MEILI_MASTER_KEY=${MEILI_MASTER_KEY}
    volumes:
      - 4dp-meili:/meili_data

  chromadb:
    image: chromadb/chroma:latest
    volumes:
      - 4dp-chroma:/chroma/chroma

  ollama:
    image: ollama/ollama:latest
    volumes:
      - 4dp-ollama:/root/.ollama
    # Uncomment for GPU support:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - capabilities: [gpu]

  worker:
    image: 4dpocket/4dpocket:latest
    command: ["4dpocket", "worker"]
    environment:
      - DATABASE_URL=postgresql://4dp:4dp@db:5432/4dpocket
      - MEILI_URL=http://meilisearch:7700
      - OLLAMA_URL=http://ollama:11434
    volumes:
      - 4dp-data:/data
    depends_on:
      - db
      - meilisearch

volumes:
  4dp-data:
  4dp-postgres:
  4dp-meili:
  4dp-chroma:
  4dp-ollama:
```

### 6.3 Configuration

All config via environment variables (12-factor), with sensible defaults:

```toml
# ~/.4dpocket/config.toml (native mode)

[server]
host = "0.0.0.0"
port = 4040
workers = 4

[database]
# "sqlite" for local, "postgresql" for docker/multi-user
url = "sqlite:///~/.4dpocket/data.db"

[search]
meili_url = "http://localhost:7700"
meili_master_key = "auto-generated"
# Embedded meilisearch binary for native mode
embedded = true

[ai]
# "ollama", "openai", "anthropic", "gemini", "disabled"
provider = "ollama"
ollama_url = "http://localhost:11434"
ollama_model = "llama3.2"
# openai_api_key = ""
# anthropic_api_key = ""
auto_tag = true
auto_summarize = true
embedding_model = "all-MiniLM-L6-v2"

[storage]
path = "~/.4dpocket"
max_archive_size_mb = 50
screenshot_quality = 80

[auth]
# "single" (no login needed), "multi" (jwt auth)
mode = "single"
secret_key = "auto-generated"
```

---

## 7. Implementation Roadmap

### Phase 1 — Foundation (Weeks 1-4)

**Week 1: Project Setup & Core Backend**
- [ ] Initialize Python project with `uv`, configure `pyproject.toml`
- [ ] Set up FastAPI application structure
- [ ] Implement SQLModel data models (KnowledgeItem, Note, Tag, Collection, User, Share) + Alembic migrations
- [ ] Basic CRUD API for knowledge items and notes
- [ ] JWT authentication (single-user mode first, multi-user ready)
- [ ] Configuration system (pydantic-settings)
- [ ] Dockerfile + docker-compose.yml

**Week 2: Processor Registry & Core Processors**
- [ ] BaseProcessor interface + processor registry + URL pattern matching
- [ ] Extraction pipeline orchestrator (fetch → extract → media → enrich → index)
- [ ] Generic URL processor (metadata, readability, archival)
- [ ] YouTube processor (yt-dlp, transcript, chapters)
- [ ] Reddit processor (JSON API, comments)
- [ ] GitHub processor (API, README, issues/PRs)
- [ ] Twitter/X processor (Nitter/FixTweet, thread unrolling)
- [ ] Instagram processor (instaloader, captions, media)
- [ ] Image processor (OCR) + PDF processor (text extraction)
- [ ] Background worker setup (ARQ/Huey)
- [ ] Page archival with monolith + screenshot capture with Playwright

**Week 3: Search, AI & Smart Tags**
- [ ] Meilisearch integration + user-scoped indexing pipeline
- [ ] Full-text search API with filters
- [ ] Ollama integration for auto-tagging with confidence scores
- [ ] Smart tag hierarchy inference (auto-nesting)
- [ ] Auto-summarization pipeline
- [ ] Sentence-transformer embeddings + ChromaDB semantic search
- [ ] **Related items engine** (semantic similarity + shared tags + same source)
- [ ] Related items surfacing on save ("here's what's related in your pocket")
- [ ] OpenAI/Anthropic fallback providers
- [ ] Duplicate detection (URL match + content similarity)

**Week 4: PWA Frontend (Core)**
- [ ] Vite + React + TypeScript project setup
- [ ] Tailwind CSS + shadcn/ui setup
- [ ] API client generation from OpenAPI spec
- [ ] Layout shell (sidebar, responsive)
- [ ] Dashboard page (recent items, stats, trending tags)
- [ ] Add item flow (paste URL → processor detection → preview + related items → save)
- [ ] Knowledge base view (grid + list toggle, filter by platform/tag/date)
- [ ] Item detail page with related items sidebar
- [ ] Note editor (markdown, standalone + attached to items)
- [ ] Tag management with hierarchy visualization

### Phase 2 — Intelligence & Sharing (Weeks 5-8)

**Week 5: Search UI & Knowledge Navigation**
- [ ] Search page with instant results + semantic search toggle
- [ ] Command palette (Cmd+K)
- [ ] Filter sidebar (type, platform, tag, date, source)
- [ ] Tag cloud + tag detail page (all items with tag)
- [ ] Collection pages with drag-and-drop ordering
- [ ] "Related items" panel on every item detail page
- [ ] Collection auto-suggestions ("these items could form a collection")

**Week 6: Multi-User & Sharing**
- [ ] Multi-user registration + per-user knowledge base isolation
- [ ] Share items, collections, and tags with specific users
- [ ] Public shareable links with optional expiry
- [ ] "Shared with me" page
- [ ] Knowledge feed (follow other users' public items)
- [ ] Comments on shared items
- [ ] User roles (admin, user, guest)

**Week 7: Extended Processors & Smart Features**
- [ ] TikTok processor (yt-dlp)
- [ ] Threads processor (Playwright scraping)
- [ ] Hacker News processor (Algolia API + linked article)
- [ ] Stack Overflow processor (SE API)
- [ ] Mastodon processor (auto-instance detection)
- [ ] Substack + Medium processors
- [ ] Spotify processor (oEmbed)
- [ ] LinkedIn processor (public posts)
- [ ] Smart collections (auto-populated by query)
- [ ] Tag evolution suggestions (merge/split)
- [ ] Trending topics dashboard
- [ ] Automation rules engine
- [ ] Import from Chrome bookmarks, Pocket, Karakeep, Raindrop.io

**Week 8: PWA, Mobile & Hardening**
- [ ] Service worker + offline support
- [ ] PWA manifest + install prompt
- [ ] Mobile-optimized bottom navigation + touch gestures
- [ ] Pull-to-refresh + push notifications
- [ ] Export (JSON, Markdown, HTML, PDF)
- [ ] Comprehensive API tests (pytest)
- [ ] Frontend component tests (Vitest)
- [ ] E2E tests (Playwright)
- [ ] Performance optimization + security audit
- [ ] Documentation + CI/CD pipeline

### Phase 3 — Platform Expansion (Weeks 9-12)
- [ ] Browser extension (Chrome + Firefox) with highlight capture
- [ ] macOS menubar app
- [ ] CLI tool (`4dp` command)
- [ ] Read-it-later mode with TTS + progress tracking
- [ ] Knowledge gaps detection + stale content flagging
- [ ] Cross-platform connection detection (link graph)
- [ ] Public demo instance

---

## 8. Key Differentiators vs Karakeep

### 8.1 Fundamental Positioning Difference

**Karakeep** is a bookmark manager — it stores links and organizes them.
**4DPocket** is a **personal knowledge base** — it captures, understands, connects, and resurfaces knowledge from across the entire internet.

| Dimension | Karakeep | 4DPocket |
|---|---|---|
| **Mental model** | "Save this link" | "Add this to my knowledge base" |
| **Multi-user** | Shared database with permissions | Per-user knowledge bases with selective sharing |
| **Platform coverage** | Links, notes, images, PDFs | 15+ platforms with deep extraction (Instagram, TikTok, Threads, HN, SO, Mastodon, etc.) |
| **Content depth** | Saves URL + metadata | Extracts full content: captions, transcripts, comments, media, thread context |
| **Knowledge connections** | Tags + lists | AI-powered related items, knowledge graph, smart collections |
| **Sharing** | Collaborative lists | Share items, collections, tags, public links, knowledge feeds between users |

### 8.2 Feature Parity Checklist

Everything Karakeep has, we have:

| Karakeep Feature | 4DPocket Equivalent | Status |
|---|---|---|
| Bookmark links, notes, images, PDFs | Same + code snippets, 15+ platform processors | Enhanced |
| Auto metadata fetch (title, desc, OG image) | Same + deep platform-specific extraction | Enhanced |
| AI auto-tagging (OpenAI + Ollama) | Same + Anthropic + Gemini + local sentence-transformers | Enhanced |
| AI summarization | Same + multi-provider + knowledge connections | Enhanced |
| Meilisearch full-text search | Same + semantic vector search (hybrid) | Enhanced |
| Full-page archival (monolith) | Same + platform media archival | Enhanced |
| Screenshot capture | Same (Playwright) | Parity |
| OCR image text extraction | Same (pytesseract + EasyOCR) | Parity |
| Video archival (yt-dlp) | Same + transcript + chapters + TikTok + Reels | Enhanced |
| Lists / collections | Same + smart collections (auto-populate by query) | Enhanced |
| Collaborative lists (viewer/editor) | Per-user knowledge bases + granular sharing | Enhanced |
| Highlights | Enhanced: color-coded, annotated, searchable, exportable | Enhanced |
| Browser extensions (Chrome/Firefox) | Same + highlight capture sidebar | Enhanced |
| iOS & Android apps | PWA first (works day 1), native apps Phase 3 | Different approach |
| RSS feed auto-hoarding | Same + configurable intervals + content-type routing | Enhanced |
| Rules engine | Same + AI-powered conditions + incoming webhooks | Enhanced |
| Import (Chrome, Pocket, Linkwarden, Omnivore, TSM) | Same + Raindrop.io + Pinboard | Enhanced |
| Browser bookmark sync (Floccus) | Same | Parity |
| SSO support | Removed from scope | N/A |
| REST API | Same (OpenAPI auto-docs) + sharing & feed APIs | Enhanced |
| Bulk actions | Same + bulk AI re-process | Enhanced |
| Multi-language (i18n) | Same | Parity |
| Dark mode | Same + system-aware auto-toggle | Parity |
| Docker deployment | Same + native pip install option | Enhanced |

### 8.3 What 4DPocket Does Better

| Aspect | Karakeep | 4DPocket |
|---|---|---|
| **Concept** | Bookmark manager | Personal knowledge base / magic library |
| **Language** | TypeScript/Node.js | Python — richer ML/AI ecosystem, easier local model integration |
| **Install** | Docker required | `pip install` for native, Docker optional |
| **Platform Coverage** | Generic URLs + basic processors | 15+ dedicated platform processors (Instagram, TikTok, Threads, HN, SO, Mastodon, Medium, Substack, Spotify, etc.) |
| **Content Extraction** | URL + metadata | Deep extraction: full text, captions, transcripts, comments, thread context, media download |
| **Multi-User** | Shared database | Per-user knowledge bases with selective sharing |
| **Sharing** | Collaborative lists | Share items/collections/tags, public links with expiry, knowledge feeds |
| **Search** | Meilisearch only | Meilisearch + Semantic vector search (hybrid) |
| **AI Providers** | OpenAI + Ollama | OpenAI + Anthropic + Gemini + Ollama + local embeddings |
| **Knowledge Graph** | None | AI-powered connections between items, related items, smart collections |
| **Frontend** | Next.js SSR | React PWA — true offline, installable, lighter |
| **Mobile** | React Native apps (separate codebase) | PWA-first (works everywhere day 1), native apps later |
| **Database** | Server-required | SQLite default (zero-config), PostgreSQL optional |
| **Highlights** | Basic highlights | Color-coded, annotated, searchable, dedicated page, exportable |
| **RSS** | Hourly polling only | Configurable intervals + content-type-aware processing |
| **Rules Engine** | Condition-action | + AI-powered conditions + incoming webhooks + templates |
| **Backup** | Basic | Scheduled + S3/WebDAV destinations |
| **Reader Mode** | None | Full reader view + TTS + progress tracking |
| **Theme** | Standard bookmark app | Doraemon's 4D Pocket — playful, magical, delightful UX |

---

## 9. Design Language — "4D Pocket"

### Visual Identity
- **Primary Color**: Doraemon Blue (`#0096C7`) with warm accents
- **Mascot/Icon**: Stylized 4D pocket opening animation
- **Typography**: Inter (UI) + JetBrains Mono (code)
- **Design System**: Clean, rounded, friendly — not corporate. Micro-animations on save (item "drops" into pocket), search (items "fly out" of pocket)

### UX Mottos
- "Toss it in" — saving should feel effortless
- "Reach in and grab" — retrieval should feel magical
- "It's always there" — archival gives confidence nothing is lost

---

## 10. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Search latency | < 50ms (Meilisearch), < 200ms (semantic) |
| Page load (PWA) | < 1.5s first load, < 300ms subsequent |
| Bookmark save | < 2s (metadata), < 30s (full archival) |
| Concurrent users | 50+ (Docker/PostgreSQL mode) |
| Storage | ~1MB per archived page average |
| Uptime | Self-hosted, user-managed |
| Accessibility | WCAG 2.1 AA compliance |
| Security | OWASP Top 10 compliant, bcrypt passwords, JWT with refresh tokens |

---

## 11. Reference: Karakeep Analysis Strategy

Before implementation begins, the development agent should:

1. **Clone Karakeep** into a temp directory for reference:
   ```bash
   git clone --depth 1 https://github.com/karakeep-app/karakeep.git /tmp/karakeep-ref
   ```

2. **Study these specific areas:**
   - `/apps/web/` — UI patterns, component structure, responsive design
   - `/apps/workers/` — Background job architecture, content processing pipeline
   - `/packages/trpc/` — API design patterns (translate to FastAPI)
   - `/packages/db/` — Data model, schema design (translate to SQLModel)
   - `/apps/mobileapp/` — Mobile UX patterns for PWA reference
   - `/docker/` — Docker setup, service orchestration
   - Content processors (how they handle different URL types)
   - Meilisearch integration (indexing strategy, search config)
   - AI integration (Ollama setup, prompt engineering for tagging)

3. **Extract best practices, not code** — 4DPocket is Python-native, so we adapt patterns, not copy TypeScript.

---

## 12. Success Metrics

| Metric | Target |
|---|---|
| Time to first bookmark | < 30 seconds from install |
| Search success rate | > 90% of items found on first query |
| AI tag accuracy | > 80% relevant tags |
| PWA Lighthouse score | > 95 |
| Docker startup time | < 60 seconds (all services healthy) |
| Daily active retrieval | Users searching/finding > saving (retrieval-first proof) |

---

*This PRD is a living document. Update as features are implemented and user feedback is gathered.*
