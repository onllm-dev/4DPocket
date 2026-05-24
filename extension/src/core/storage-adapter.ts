// Firefox uses the `browser` global (WebExtension API) which returns Promises.
// Chrome uses `chrome.storage.local` which also returns Promises in MV3.
// We prefer `browser` when available (Firefox) to avoid the callback-style
// chrome.storage.local.get() that returns undefined and breaks await chains.
declare const browser: any;

export function createStorageAdapter() {
  // Access browser via globalThis to avoid TS "browser is not defined" errors
  const storageApi =
    typeof globalThis.browser !== "undefined" && globalThis.browser?.storage?.local
      ? globalThis.browser.storage.local
      : chrome.storage.local;

  return {
    get: (keys: string[]) => storageApi.get(keys),
    set: (items: Record<string, unknown>) => storageApi.set(items),
    remove: (keys: string[]) => storageApi.remove(keys),
  };
}