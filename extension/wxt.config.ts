import { defineConfig } from "wxt";

export default defineConfig({
  srcDir: "src",
  outDir: "dist",
  manifest: {
    name: "4DPocket",
    description: "Save anything to your AI-powered knowledge base",
    permissions: ["activeTab", "tabs", "contextMenus", "storage", "sidePanel"],
    host_permissions: ["http://*/*", "https://*/*"],
    icons: {
      16: "icon/16.png",
      32: "icon/32.png",
      48: "icon/48.png",
      128: "icon/128.png",
    },
  },
});
