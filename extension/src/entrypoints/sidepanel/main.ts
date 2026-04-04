import { setStorageAdapter, getStoredAuth } from "../../core/api-client";
import { validateToken } from "../../core/auth";
import { checkUrl } from "../../core/items";
import { getHighlightsForItem } from "../../core/highlights";
import type { HighlightRead } from "../../core/types";

// Initialize storage adapter for Chrome
setStorageAdapter({
  get: (keys) => chrome.storage.local.get(keys),
  set: (items) => chrome.storage.local.set(items),
  remove: (keys) => chrome.storage.local.remove(keys),
});

// State elements
const states = {
  loading: document.getElementById("state-loading")!,
  notConnected: document.getElementById("state-not-connected")!,
  empty: document.getElementById("state-empty")!,
  notSaved: document.getElementById("state-not-saved")!,
  highlights: document.getElementById("state-highlights")!,
  error: document.getElementById("state-error")!,
};

const pageInfo = document.getElementById("page-info")!;
const highlightsList = document.getElementById("highlights-list")!;
const errorMessage = document.getElementById("error-message")!;
const openOptionsBtn = document.getElementById("open-options")!;
const retryBtn = document.getElementById("retry-btn")!;

let currentUrl = "";

function showState(stateName: keyof typeof states) {
  for (const el of Object.values(states)) {
    el.classList.remove("active");
  }
  states[stateName].classList.add("active");
}

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function renderHighlights(highlights: HighlightRead[]) {
  highlightsList.innerHTML = "";

  for (const h of highlights) {
    const card = document.createElement("div");
    card.className = "highlight-card";
    card.style.borderLeftColor = h.color || "#FCD34D";

    let html = `<p class="highlight-text">\u201C${escapeHtml(h.text)}\u201D</p>`;
    html += `<div class="highlight-meta">`;
    html += `<span class="highlight-color" style="background: ${h.color || "#FCD34D"}"></span>`;
    html += `<span class="highlight-time">${timeAgo(h.created_at)}</span>`;
    html += `</div>`;

    if (h.note) {
      html += `<p class="highlight-note">${escapeHtml(h.note)}</p>`;
    }

    card.innerHTML = html;
    highlightsList.appendChild(card);
  }
}

function escapeHtml(text: string): string {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

async function loadHighlightsForUrl(url: string) {
  if (!url || url.startsWith("chrome://") || url.startsWith("chrome-extension://")) {
    pageInfo.textContent = "Browser pages not supported";
    showState("empty");
    return;
  }

  currentUrl = url;
  showState("loading");

  try {
    const auth = await getStoredAuth();
    if (!auth.serverUrl) {
      showState("notConnected");
      return;
    }

    if (!auth.token) {
      showState("notConnected");
      return;
    }

    const user = await validateToken();
    if (!user) {
      showState("notConnected");
      return;
    }

    // Check if page is saved
    const check = await checkUrl(url);
    if (!check.exists || !check.item_id) {
      showState("notSaved");
      return;
    }

    pageInfo.textContent = check.title || url;

    // Fetch highlights
    const highlights = await getHighlightsForItem(check.item_id);

    if (highlights.length === 0) {
      showState("empty");
      return;
    }

    renderHighlights(highlights);
    showState("highlights");
  } catch (err) {
    errorMessage.textContent =
      err instanceof Error ? err.message : "Failed to load highlights";
    showState("error");
  }
}

// Event listeners
openOptionsBtn.addEventListener("click", () => chrome.runtime.openOptionsPage());

retryBtn.addEventListener("click", () => {
  if (currentUrl) loadHighlightsForUrl(currentUrl);
});

// Listen for tab changes
chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  const tab = await chrome.tabs.get(tabId);
  if (tab.url) loadHighlightsForUrl(tab.url);
});

chrome.tabs.onUpdated.addListener((_tabId, changeInfo) => {
  if (changeInfo.url) loadHighlightsForUrl(changeInfo.url);
});

// Initial load
async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.url) {
    loadHighlightsForUrl(tab.url);
  } else {
    showState("empty");
  }
}

init();
