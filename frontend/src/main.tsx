import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { queryClient } from "./lib/query-client";
import "./styles/globals.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);

// Register service worker in production; unregister any lingering SW in dev
// so it can't intercept Vite module requests with stale cached hashes.
if ("serviceWorker" in navigator) {
  if (import.meta.env.PROD) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    });
  } else {
    navigator.serviceWorker.getRegistrations().then((regs) => {
      regs.forEach((r) => r.unregister());
    });
    if ("caches" in window) {
      caches.keys().then((keys) => keys.forEach((k) => caches.delete(k)));
    }
  }
}

// Auto-recover from stale dynamic-import chunks after a deploy:
// if a lazy-loaded route chunk 404s because Vite changed the hash,
// do one hard reload per session to pick up the new index.html.
window.addEventListener("vite:preloadError", () => {
  if (!sessionStorage.getItem("fdp_reloaded_for_stale_chunk")) {
    sessionStorage.setItem("fdp_reloaded_for_stale_chunk", "1");
    window.location.reload();
  }
});
