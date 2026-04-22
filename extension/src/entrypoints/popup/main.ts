import { setStorageAdapter, getStoredAuth } from "../../core/api-client";
import { validateToken } from "../../core/auth";
import { checkUrl, saveItem } from "../../core/items";

// Initialize storage adapter for Chrome
setStorageAdapter({
  get: (keys) => chrome.storage.local.get(keys),
  set: (items) => chrome.storage.local.set(items),
  remove: (keys) => chrome.storage.local.remove(keys),
});

function must<T extends HTMLElement>(id: string): T {
  const el = document.getElementById(id);
  if (!el) throw new Error(`popup: missing DOM element #${id}`);
  return el as T;
}

// State elements
const states = {
  notConnected: must("state-not-connected"),
  notLoggedIn: must("state-not-logged-in"),
  loading: must("state-loading"),
  ready: must("state-ready"),
  saving: must("state-saving"),
  saved: must("state-saved"),
  alreadySaved: must("state-already-saved"),
  error: must("state-error"),
};

const footer = must("footer");
const footerUsername = must("footer-username");

// Interactive elements
const saveBtn = must<HTMLButtonElement>("save-btn");
const retryBtn = must<HTMLButtonElement>("retry-btn");
const viewSavedBtn = must<HTMLButtonElement>("view-saved-btn");
const viewExistingBtn = must<HTMLButtonElement>("view-existing-btn");
const openOptionsConnect = must<HTMLButtonElement>("open-options-connect");
const openOptionsLogin = must<HTMLButtonElement>("open-options-login");
const openSettings = must<HTMLButtonElement>("open-settings");

// Display elements
const pageTitle = must("page-title");
const pageUrl = must("page-url");
const savedSubtitle = must("saved-subtitle");
const alreadySavedTitle = must("already-saved-title");
const errorDetail = must("error-detail");

// Current tab info
let currentTab: { url: string; title: string } = { url: "", title: "" };
let serverUrl = "";
let savedItemId = "";

function showState(stateName: keyof typeof states) {
  for (const el of Object.values(states)) {
    el.classList.remove("active");
  }
  states[stateName].classList.add("active");
}

function showFooter(username: string) {
  footer.style.display = "flex";
  footerUsername.textContent = username;
}

function openInNewTab(url: string) {
  chrome.tabs.create({ url });
}

// Event listeners
openOptionsConnect.addEventListener("click", () => chrome.runtime.openOptionsPage());
openOptionsLogin.addEventListener("click", () => chrome.runtime.openOptionsPage());
openSettings.addEventListener("click", () => chrome.runtime.openOptionsPage());

saveBtn.addEventListener("click", () => doSave());
retryBtn.addEventListener("click", () => doSave());

viewSavedBtn.addEventListener("click", () => {
  if (savedItemId && serverUrl) {
    openInNewTab(`${serverUrl}/item/${savedItemId}`);
  }
});

viewExistingBtn.addEventListener("click", () => {
  if (savedItemId && serverUrl) {
    openInNewTab(`${serverUrl}/item/${savedItemId}`);
  }
});

async function doSave() {
  if (saveBtn.disabled) return;
  saveBtn.disabled = true;
  showState("saving");

  try {
    const result = await saveItem(currentTab.url, currentTab.title);

    if (result.status === "duplicate") {
      savedItemId = result.existingId;
      alreadySavedTitle.textContent = result.title || currentTab.title || "This page";
      showState("alreadySaved");
    } else {
      savedItemId = result.item.id;
      savedSubtitle.textContent = result.item.title || currentTab.title || "Saved";
      showState("saved");
    }
  } catch (err) {
    errorDetail.textContent = err instanceof Error ? err.message : "An unexpected error occurred";
    showState("error");
  } finally {
    saveBtn.disabled = false;
  }
}

async function init() {
  saveBtn.disabled = true;
  showState("loading");

  // 1. Check server URL configured
  const auth = await getStoredAuth();
  serverUrl = auth.serverUrl;

  if (!serverUrl) {
    showState("notConnected");
    return;
  }

  // 2. Check authentication
  if (!auth.token) {
    showState("notLoggedIn");
    return;
  }

  const user = await validateToken();
  if (!user) {
    showState("notLoggedIn");
    return;
  }

  showFooter(user.username);

  // 3. Get current tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab?.url || tab.url.startsWith("chrome://") || tab.url.startsWith("chrome-extension://")) {
    pageTitle.textContent = "Cannot save this page";
    pageUrl.textContent = "Browser internal pages are not supported";
    showState("ready");
    saveBtn.disabled = true;
    return;
  }

  currentTab = { url: tab.url, title: tab.title || "" };
  pageTitle.textContent = currentTab.title || currentTab.url;
  pageUrl.textContent = currentTab.url;

  // 4. Check if already saved
  try {
    const check = await checkUrl(currentTab.url);
    if (check.exists && check.item_id) {
      savedItemId = check.item_id;
      alreadySavedTitle.textContent = check.title || currentTab.title || "This page";
      showState("alreadySaved");
      return;
    }
  } catch {
    // If check fails, just show ready state - user can still try to save
  }

  saveBtn.disabled = false;
  showState("ready");
}

init().catch((err) => {
  errorDetail.textContent = err instanceof Error ? err.message : "An unexpected error occurred";
  showState("error");
});
