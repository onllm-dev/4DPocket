import { setStorageAdapter, getStoredAuth } from "../core/api-client";
import { saveItem, checkUrl } from "../core/items";
import { createHighlight } from "../core/highlights";

export default defineBackground(() => {
  // Initialize storage adapter for Chrome (must happen before any core calls)
  setStorageAdapter({
    get: (keys) => chrome.storage.local.get(keys),
    set: (items) => chrome.storage.local.set(items),
    remove: (keys) => chrome.storage.local.remove(keys),
  });

  // --- Badge helpers ---

  function showBadge(text: string, color: string, tabId?: number) {
    const opts: chrome.action.BadgeTextDetails = { text };
    if (tabId !== undefined) opts.tabId = tabId;
    chrome.action.setBadgeText(opts);
    chrome.action.setBadgeBackgroundColor({ color, ...(tabId !== undefined ? { tabId } : {}) });
    setTimeout(() => {
      const clearOpts: chrome.action.BadgeTextDetails = { text: "" };
      if (tabId !== undefined) clearOpts.tabId = tabId;
      chrome.action.setBadgeText(clearOpts);
    }, 2000);
  }

  // --- Highlight save helper ---

  async function resolveItemId(url: string, title?: string): Promise<string> {
    const check = await checkUrl(url);
    if (check.exists && check.item_id) {
      return check.item_id;
    }
    const result = await saveItem(url, title);
    if (result.status === "duplicate") {
      return result.existingId;
    }
    return result.item.id;
  }

  async function handleSaveHighlight(data: {
    url: string;
    title: string;
    text: string;
    context: string;
    position: { selector: string; textOffset: number; textLength: number };
  }) {
    const { serverUrl, token } = await getStoredAuth();
    if (!serverUrl || !token) throw new Error("Not authenticated");

    const itemId = await resolveItemId(data.url, data.title);

    return createHighlight({
      item_id: itemId,
      text: data.text,
      position: {
        selector: data.position.selector,
        textOffset: data.position.textOffset,
        textLength: data.position.textLength,
        context: data.context,
      },
    });
  }

  // --- Feature 5: Content script highlight messages ---

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // Only accept messages from our own extension's content scripts
    if (!sender.id || sender.id !== chrome.runtime.id) {
      sendResponse({ status: "error", message: "Unauthorized sender" });
      return false;
    }
    if (message.type === "SAVE_HIGHLIGHT") {
      if (!message.data?.url || !message.data?.text) {
        sendResponse({ status: "error", message: "Missing required fields" });
        return false;
      }
      handleSaveHighlight(message.data).then(
        (result) => sendResponse({ status: "success", data: result }),
        () => sendResponse({ status: "error", message: "Failed to save highlight" })
      );
      return true; // Keep message channel open for async response
    }
  });

  // --- Feature 3: Context Menu Save ---

  chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
      id: "save-page",
      title: "Save Page to 4DPocket",
      contexts: ["page"],
    });
    chrome.contextMenus.create({
      id: "save-highlight",
      title: "Save Highlight to 4DPocket",
      contexts: ["selection"],
    });
  });

  chrome.contextMenus.onClicked.addListener(async (info, tab) => {
    if (!tab?.id) return;
    const tabId = tab.id;
    const url = info.pageUrl || tab.url;
    if (!url) return;

    if (info.menuItemId === "save-page") {
      try {
        const { serverUrl, token } = await getStoredAuth();
        if (!serverUrl || !token) {
          showBadge("!", "#dc2626", tabId);
          return;
        }
        await saveItem(url, tab.title);
        showBadge("\u2713", "#16a34a", tabId);
      } catch {
        showBadge("!", "#dc2626", tabId);
      }
    }

    if (info.menuItemId === "save-highlight" && info.selectionText) {
      try {
        const { serverUrl, token } = await getStoredAuth();
        if (!serverUrl || !token) {
          showBadge("!", "#dc2626", tabId);
          return;
        }
        const itemId = await resolveItemId(url, tab.title);
        await createHighlight({ item_id: itemId, text: info.selectionText });
        showBadge("\u2713", "#16a34a", tabId);
      } catch {
        showBadge("!", "#dc2626", tabId);
      }
    }
  });

  // --- Feature 4: Auto-detect already saved (badge on navigation) ---

  async function updateBadgeForTab(tabId: number, url: string) {
    if (!url.startsWith("http")) {
      chrome.action.setBadgeText({ text: "", tabId });
      return;
    }

    try {
      const { serverUrl, token } = await getStoredAuth();
      if (!serverUrl || !token) return;

      const result = await checkUrl(url);
      if (result.exists) {
        chrome.action.setBadgeText({ text: "\u2713", tabId });
        chrome.action.setBadgeBackgroundColor({ color: "#16a34a", tabId });
      } else {
        chrome.action.setBadgeText({ text: "", tabId });
      }
    } catch {
      // Silently ignore - badge is a nice-to-have
    }
  }

  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === "complete" && tab.url) {
      updateBadgeForTab(tabId, tab.url);
    }
  });

  chrome.tabs.onActivated.addListener(async ({ tabId }) => {
    const tab = await chrome.tabs.get(tabId);
    if (tab.url) {
      updateBadgeForTab(tabId, tab.url);
    }
  });

  // Background service worker ready
});
