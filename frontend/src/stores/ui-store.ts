import { create } from "zustand";
import { persist } from "zustand/middleware";

type Theme = "light" | "dark" | "system";
type ViewMode = "grid" | "list";

interface UIState {
  theme: Theme;
  sidebarCollapsed: boolean;
  viewMode: ViewMode;
  setTheme: (theme: Theme) => void;
  toggleSidebar: () => void;
  setViewMode: (mode: ViewMode) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      theme: "system",
      sidebarCollapsed: false,
      viewMode: "grid",
      setTheme: (theme) => {
        set({ theme });
        applyTheme(theme);
      },
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setViewMode: (viewMode) => set({ viewMode }),
    }),
    { name: "4dp-ui-preferences" }
  )
);

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") {
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches;
    root.classList.toggle("dark", prefersDark);
  } else {
    root.classList.toggle("dark", theme === "dark");
  }
}

// Apply theme on load
if (typeof window !== "undefined") {
  try {
    const stored = JSON.parse(
      localStorage.getItem("4dp-ui-preferences") || "{}"
    );
    applyTheme(stored?.state?.theme || "system");
  } catch {
    applyTheme("system");
  }
}
