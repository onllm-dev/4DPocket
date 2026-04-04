import { setStorageAdapter, getStoredAuth } from "../../core/api-client";
import { validateToken } from "../../core/auth";
import { checkUrl, saveItem } from "../../core/items";

// Initialize storage adapter for Chrome
setStorageAdapter({
  get: (keys) => chrome.storage.local.get(keys),
  set: (items) => chrome.storage.local.set(items),
  remove: (keys) => chrome.storage.local.remove(keys),
});

// State elements
const states = {
  notConnected: document.getElementById("state-not-connected")!,
  notLoggedIn: document.getElementById("state-not-logged-in")!,
  loading: document.getElementById("state-loading")!,
  ready: document.getElementById("state-ready")!,
  saving: document.getElementById("state-saving")!,
  saved: document.getElementById("state-saved")!,
  alreadySaved: document.getElementById("state-already-saved")!,
  error: document.getElementById("state-error")!,
};

const footer = document.getElementById("footer")!;
const footerUsername = document.getElementById("footer-username")!;

// Interactive elements
const saveBtn = document.getElementById("save-btn") as HTMLButtonElement;
const retryBtn = document.getElementById("retry-btn") as HTMLButtonElement;
const viewSavedBtn = document.getElementById("view-saved-btn") as HTMLButtonElement;
const viewExistingBtn = document.getElementById("view-existing-btn") as HTMLButtonElement;
const openOptionsConnect = document.getElementById("open-options-connect") as HTMLButtonElement;
const openOptionsLogin = document.getElementById("open-options-login") as HTMLButtonElement;
const openSettings = document.getElementById("open-settings") as HTMLButtonElement;

// Display elements
const pageTitle = document.getElementById("page-title")!;
const pageUrl = document.getElementById("page-url")!;
const savedSubtitle = document.getElementById("saved-subtitle")!;
const alreadySavedTitle = document.getElementById("already-saved-title")!;
const errorDetail = document.getElementById("error-detail")!;

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
  }
}

async function init() {
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

  showState("ready");
}

init();
