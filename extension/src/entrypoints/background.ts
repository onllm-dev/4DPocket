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
    } else {
      sendResponse({ status: "error", message: `unknown message type: ${message?.type}` });
      return false;
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

  // Track tabs that currently show a transient "?" badge so we can clear it
  // on the next successful update rather than leaving it indefinitely.
  const transientBadgeTabs = new Set<number>();

  async function updateBadgeForTab(tabId: number, url: string) {
    if (!url.startsWith("http")) {
      chrome.action.setBadgeText({ text: "", tabId });
      transientBadgeTabs.delete(tabId);
      return;
    }

    try {
      const { serverUrl, token } = await getStoredAuth();
      if (!serverUrl || !token) return;

      const result = await checkUrl(url);
      // Success path — clear any lingering "?" badge first
      transientBadgeTabs.delete(tabId);
      if (result.exists) {
        chrome.action.setBadgeText({ text: "\u2713", tabId });
        chrome.action.setBadgeBackgroundColor({ color: "#16a34a", tabId });
      } else {
        chrome.action.setBadgeText({ text: "", tabId });
      }
    } catch (err) {
      // Network error / 5xx / auth error — log and show "?" with gray.
      // Mark this tab so the badge is cleared on the next success.
      console.warn("[4dp] badge update failed", err);
      transientBadgeTabs.add(tabId);
      chrome.action.setBadgeText({ text: "?", tabId });
      chrome.action.setBadgeBackgroundColor({ color: "#6b7280", tabId });
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
