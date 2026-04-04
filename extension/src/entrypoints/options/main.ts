import { setStorageAdapter, getStoredAuth, setStoredAuth } from "../../core/api-client";
import { testConnection, login, validateToken, logout } from "../../core/auth";
import { DEFAULT_SERVER_URL } from "../../core/constants";

// Initialize storage adapter for Chrome
setStorageAdapter({
  get: (keys) => chrome.storage.local.get(keys),
  set: (items) => chrome.storage.local.set(items),
  remove: (keys) => chrome.storage.local.remove(keys),
});

// DOM elements
const serverUrlInput = document.getElementById("server-url") as HTMLInputElement;
const testBtn = document.getElementById("test-btn") as HTMLButtonElement;
const connectionStatus = document.getElementById("connection-status")!;
const loginForm = document.getElementById("login-form") as HTMLFormElement;
const usernameInput = document.getElementById("username") as HTMLInputElement;
const passwordInput = document.getElementById("password") as HTMLInputElement;
const loginBtn = document.getElementById("login-btn") as HTMLButtonElement;
const loginError = document.getElementById("login-error")!;
const loginFormContainer = document.getElementById("login-form-container")!;
const loggedInContainer = document.getElementById("logged-in-container")!;
const usernameDisplay = document.getElementById("username-display")!;
const logoutBtn = document.getElementById("logout-btn") as HTMLButtonElement;

function showStatus(el: HTMLElement, message: string, type: "success" | "error") {
  el.textContent = message;
  el.className = `status status-${type}`;
  el.classList.remove("hidden");
}

function hideStatus(el: HTMLElement) {
  el.classList.add("hidden");
}

function showLoggedIn(username: string) {
  loginFormContainer.classList.add("hidden");
  loggedInContainer.classList.remove("hidden");
  usernameDisplay.textContent = username;
}

function showLoginForm() {
  loginFormContainer.classList.remove("hidden");
  loggedInContainer.classList.add("hidden");
  hideStatus(loginError);
}

// Initialize
async function init() {
  const auth = await getStoredAuth();
  serverUrlInput.value = auth.serverUrl || DEFAULT_SERVER_URL;

  if (auth.token) {
    const user = await validateToken();
    if (user) {
      showLoggedIn(user.username);
    } else {
      showLoginForm();
    }
  } else {
    showLoginForm();
  }
}

// Test connection
testBtn.addEventListener("click", async () => {
  const url = serverUrlInput.value.trim().replace(/\/+$/, "");
  if (!url) return;

  testBtn.disabled = true;
  testBtn.textContent = "Testing...";
  hideStatus(connectionStatus);

  const ok = await testConnection(url);

  if (ok) {
    showStatus(connectionStatus, "Connected successfully!", "success");
    await setStoredAuth({ serverUrl: url });
  } else {
    showStatus(connectionStatus, "Could not connect. Check the URL and ensure the server is running.", "error");
  }

  testBtn.disabled = false;
  testBtn.textContent = "Test";
});

// Login
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const serverUrl = serverUrlInput.value.trim().replace(/\/+$/, "");
  const username = usernameInput.value.trim();
  const password = passwordInput.value;

  if (!serverUrl || !username || !password) return;

  loginBtn.disabled = true;
  loginBtn.textContent = "Logging in...";
  hideStatus(loginError);

  try {
    await setStoredAuth({ serverUrl });
    const user = await login(serverUrl, username, password);
    showLoggedIn(user.username);
    passwordInput.value = "";
  } catch (err) {
    showStatus(loginError, err instanceof Error ? err.message : "Login failed", "error");
  }

  loginBtn.disabled = false;
  loginBtn.textContent = "Login";
});

// Logout
logoutBtn.addEventListener("click", async () => {
  await logout();
  showLoginForm();
});

init();
