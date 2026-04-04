import { defineConfig } from "wxt";

export default defineConfig({
  srcDir: "src",
  outDir: "dist",
  manifest: {
    name: "4DPocket",
    description: "Save anything to your AI-powered knowledge base",
    permissions: ["activeTab", "tabs", "contextMenus", "storage", "sidePanel"],
    host_permissions: ["<all_urls>"],
  },
});
