# 4DPocket Extension — Chrome Web Store Pre-Submission Checklist

Work through every item before submitting. Items marked **(verified)** were confirmed by reading source files. Items marked **(action needed)** require work before submission.

---

## 1. Privacy Policy

- [ ] Privacy policy URL is hosted at a publicly accessible URL
  - **(action needed)** — `PRIVACY.md` exists in this repo but must be hosted at a public URL (e.g., a GitHub Pages page or your own domain). The Chrome Web Store requires a live URL, not a repo file path.

---

## 2. Permissions Justification

Each permission declared in `wxt.config.ts` must be justified in the store submission form.

- [ ] `activeTab` — Required to read the URL and title of the current tab when the user clicks Save.
  - **(verified at `extension/src/entrypoints/popup/main.ts:143`)** — `chrome.tabs.query({ active: true, currentWindow: true })` reads the active tab.

- [ ] `tabs` — Required to open the saved item in a new tab and to update the badge per tab.
  - **(verified at `extension/src/entrypoints/popup/main.ts:66`)** — `chrome.tabs.create({ url })` and badge update logic uses `tab.id`.
  - **(verified at `extension/src/entrypoints/background.ts:176`)** — `chrome.tabs.onUpdated` listener uses tab IDs.

- [ ] `contextMenus` — Required to add right-click "Save Page to 4DPocket" and "Save Highlight to 4DPocket" menu items.
  - **(verified at `extension/src/entrypoints/background.ts:91-102`)** — `chrome.contextMenus.create(...)` in `onInstalled`.

- [ ] `storage` — Required to persist the configured server URL and authentication token locally.
  - **(verified at `extension/src/core/api-client.ts:15-26`)** — `chrome.storage.local.get/set/remove` for auth credentials.

- [ ] `sidePanel` — Required to open the side panel that lets users browse saved items alongside a web page.
  - **(verified at `extension/dist/chrome-mv3/manifest.json`)** — `"side_panel": {"default_path": "sidepanel.html"}` confirms the panel is used.

- [ ] `host_permissions: ["http://*/*", "https://*/*"]` — Required to contact the user's self-hosted backend at any URL they configure, and to check whether pages have already been saved.
  - **(verified at `extension/src/core/api-client.ts:77`)** — `fetch(`${serverUrl}${path}`, ...)` — the server URL is user-supplied and can be any host.
  - **(action needed)** — Broad host permissions require extra justification in the submission form. Prepare a written explanation: "The user configures an arbitrary server URL for their self-hosted backend. The extension cannot know this URL at build time, so broad host permissions are required to reach it."

---

## 3. Manifest V3

- [x] Manifest version is 3.
  - **(verified at `extension/dist/chrome-mv3/manifest.json:1`)** — `"manifest_version": 3`.

- [x] Background is a service worker (not a persistent background page).
  - **(verified at `extension/dist/chrome-mv3/manifest.json`)** — `"background": {"service_worker": "background.js"}`.

---

## 4. Icon Set

- [ ] Icon 16x16 present and correct
  - **(action needed)** — `wxt.config.ts` declares `icon/16.png` but no PNG files are present in `extension/dist/chrome-mv3/icon/`. Create icon files at `extension/src/assets/icon/16.png`, `32.png`, `48.png`, `128.png` and verify they are copied to the build output.

- [ ] Icon 32x32 present and correct — **(action needed)** — same as above.

- [ ] Icon 48x48 present and correct — **(action needed)** — same as above.

- [ ] Icon 128x128 present and correct — **(action needed)** — same as above.

---

## 5. Demo Video

- [ ] Demo video is under 30 seconds
  - **(action needed)** — No demo video exists yet. Record a short screencast showing: configure server URL → save a page → see the badge → open side panel. Export as MP4, confirm duration is under 30 seconds.

---

## 6. Browser Compatibility

- [ ] Tested on Chrome (latest stable)
  - **(action needed)** — Manually verify: install from `dist/chrome-mv3`, test save, highlight, context menu, badge, and side panel.

- [ ] Tested on Edge (Chromium-based, latest stable)
  - **(action needed)** — Load unpacked extension in Edge; verify all features.

- [ ] Tested on Brave (latest stable)
  - **(action needed)** — Load unpacked extension in Brave; verify all features.

---

## 7. Backend Reachability Messaging

The extension shows appropriate UI states when the backend is unreachable:

- [x] Popup shows `notConnected` state when no server URL is configured.
  - **(verified at `extension/src/entrypoints/popup/main.ts:123-126`)** — `if (!serverUrl) { showState("notConnected"); return; }`.

- [x] Popup shows `notLoggedIn` state when token is absent or invalid.
  - **(verified at `extension/src/entrypoints/popup/main.ts:129-138`)** — `if (!auth.token)` and `if (!user)` guards.

- [x] Popup shows `error` state (with message text) on network failures during save.
  - **(verified at `extension/src/entrypoints/popup/main.ts:107-109`)** — `catch (err) { errorDetail.textContent = ...; showState("error"); }`.

- [x] Background badge shows `?` (gray) when the badge update fails due to a network error.
  - **(verified at `extension/src/entrypoints/background.ts:166-173`)** — `catch (err) { ... showBadge("?", "#6b7280", tabId); }`.

- [x] Auth header is refused over plain HTTP to non-localhost servers.
  - **(verified at `extension/src/core/api-client.ts:67-73`)** — Protocol check before setting `Authorization` header.

---

## 8. Additional Store Requirements

- [ ] Store title matches `wxt.config.ts` `name`: "4DPocket"
  - **(verified at `extension/wxt.config.ts:7`)** — `name: "4DPocket"`.

- [ ] Store description matches short description in `STORE_LISTING.md`
  - **(verified at `extension/wxt.config.ts:8`)** — `description: "Save anything to your AI-powered knowledge base"`.

- [ ] Version in store matches `extension/package.json` version
  - **(verified at `extension/package.json:3`)** — current version `0.2.2`.

- [ ] Zip created with `pnpm zip` and tested as a loaded-unpacked extension before submission.
  - **(action needed)** — Run `cd extension && pnpm zip`, unpack the zip, load in Chrome, run through all features.
