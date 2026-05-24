// Cross-browser action badge adapter: prefers chrome.action (Chrome MV3)
// then browser.browserAction (Firefox MV2).
const action: any =
  typeof globalThis.chrome !== "undefined" && (globalThis as any).chrome?.action
    ? (globalThis as any).chrome.action
    : typeof globalThis.browser !== "undefined" && (globalThis as any).browser?.browserAction
      ? (globalThis as any).browser.browserAction
      : null;

export function setBadgeText(details: { text: string; tabId?: number }): void {
  if (!action) return;
  try {
    action.setBadgeText(details);
  } catch (err) {
    console.warn("[4dp] setBadgeText failed", err);
  }
}

export function setBadgeBackgroundColor(details: { color: string; tabId?: number }): void {
  if (!action) return;
  try {
    action.setBadgeBackgroundColor(details);
  } catch (err) {
    console.warn("[4dp] setBadgeBackgroundColor failed", err);
  }
}
