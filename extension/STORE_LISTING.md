# 4DPocket — Chrome Web Store Listing Draft

## Short Description (max 132 chars)

Save any web page, highlight, or link to your self-hosted AI knowledge base with one click.

_(Current length: 89 chars)_

---

## Long Description (~600 words)

**Your knowledge base. Your server. Your data.**

4DPocket is a browser extension for the 4DPocket self-hosted knowledge management platform. It lets you clip, highlight, and save content from any web page directly into your personal AI-powered knowledge base — running entirely on hardware you control.

**How it works**

Install the extension, point it at your self-hosted 4DPocket backend, and log in. From that moment, saving anything on the web is a single click (or right-click) away. The extension talks only to your server — nothing leaves your network unless you decide it should.

**Key features**

- **One-click page save** — Click the toolbar icon to save the current page. The extension records the URL and title; your backend handles content extraction, AI tagging, and summarization automatically.
- **Right-click context menu** — Right-click anywhere on a page to "Save Page to 4DPocket" without opening the popup.
- **Highlight saving** — Select any text, right-click, and choose "Save Highlight to 4DPocket". The highlight is attached to the item for the same URL, creating it first if needed.
- **Already-saved badge** — A green check mark badge on the toolbar icon tells you when the current page is already in your knowledge base, so you never duplicate saves.
- **Side panel** — Open the 4DPocket side panel to browse your recent items without leaving the current tab.

**Who this is for**

Researchers, writers, engineers, and knowledge workers who want a private, searchable archive of everything they read — without giving that archive to a cloud service. If you already run a 4DPocket backend (Docker or bare-metal), this extension is the capture layer for it.

**What you need**

A running 4DPocket backend (v0.2+). The extension does not work standalone; it is a front-end client for your own server. See the self-hosting guide at `docs/SELF_HOSTING.md` in the project repository.

**Privacy**

All data goes directly to your configured server. The extension has no telemetry, no analytics, and no third-party connections of any kind. Your authentication token is stored locally in `chrome.storage.local` and is never sent over plain HTTP to non-localhost hosts. Full privacy policy: see `PRIVACY.md` in the extension directory or the hosted version linked in the store listing.

---

## Feature Bullets (store listing, 5 items)

1. Save any page to your self-hosted knowledge base with one click or right-click
2. Highlight and annotate text passages; highlights sync to your backend automatically
3. Badge indicator shows which pages are already saved — no duplicate clipping
4. Side panel for quick browsing without leaving your current tab
5. Zero telemetry, zero third-party requests — all traffic goes only to your own server

---

## Screenshots Checklist

Generate these screenshots at 1280x800 (Chrome Web Store requirement):

| Filename | What to show |
|---|---|
| `screenshot-01-popup.png` | Toolbar popup with a page ready to save; show the green "Save" button |
| `screenshot-02-saved-badge.png` | Badge showing green checkmark on a page already in the knowledge base |
| `screenshot-03-context-menu.png` | Right-click context menu showing "Save Page to 4DPocket" and "Save Highlight" options |
| `screenshot-04-sidepanel.png` | Side panel open alongside a web page showing recent saved items |
| `screenshot-05-options.png` | Options page where users configure their server URL |

---

## Category Recommendation

**Productivity** (primary)

---

## Single-Purpose Declaration

The single purpose of this extension is to save web content (pages, text highlights, and links) to the user's self-hosted 4DPocket knowledge base. All features — save, highlight, badge, side panel — directly serve this single purpose. No advertising, no data collection, no unrelated functionality.
