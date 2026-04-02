import {
  Settings as SettingsIcon,
  Sun,
  Moon,
  Monitor,
  Grid3x3,
  List,
  Info,
  Sparkles,
} from "lucide-react";
import { useUIStore } from "@/stores/ui-store";

type Theme = "light" | "dark" | "system";
type ViewMode = "grid" | "list";

const THEMES: { value: Theme; label: string; icon: React.ReactNode }[] = [
  { value: "light", label: "Light", icon: <Sun className="h-4 w-4" /> },
  { value: "dark", label: "Dark", icon: <Moon className="h-4 w-4" /> },
  { value: "system", label: "System", icon: <Monitor className="h-4 w-4" /> },
];

const VIEW_MODES: { value: ViewMode; label: string; icon: React.ReactNode }[] = [
  { value: "grid", label: "Grid", icon: <Grid3x3 className="h-4 w-4" /> },
  { value: "list", label: "List", icon: <List className="h-4 w-4" /> },
];

export default function Settings() {
  const { theme, viewMode, setTheme, setViewMode } = useUIStore();

  return (
    <div className="animate-fade-in p-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <SettingsIcon className="h-6 w-6 text-sky-600" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Settings
        </h1>
      </div>

      <div className="space-y-6">
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5">
          <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100 mb-4">
            Appearance
          </h2>

          <div className="mb-5">
            <label className="text-xs font-medium uppercase tracking-wider text-gray-600 dark:text-gray-400 block mb-3">
              Theme
            </label>
            <div className="flex gap-2">
              {THEMES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setTheme(t.value)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 flex-1 justify-center cursor-pointer ${
                    theme === t.value
                      ? "bg-sky-600 text-white"
                      : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-md"
                  }`}
                >
                  {t.icon}
                  <span>{t.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-medium uppercase tracking-wider text-gray-600 dark:text-gray-400 block mb-3">
              Default View Mode
            </label>
            <div className="flex gap-2">
              {VIEW_MODES.map((m) => (
                <button
                  key={m.value}
                  onClick={() => setViewMode(m.value)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 flex-1 justify-center cursor-pointer ${
                    viewMode === m.value
                      ? "bg-sky-600 text-white"
                      : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-md"
                  }`}
                >
                  {m.icon}
                  <span>{m.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="h-4 w-4 text-sky-600" />
            <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100">
              AI Provider
            </h2>
          </div>
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-sm text-gray-900 dark:text-gray-100 font-medium">
                Provider
              </p>
              <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
                Server-side configuration
              </p>
            </div>
            <span className="text-xs text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 px-3 py-1.5 rounded-lg">
              Configured on server
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5">
          <div className="flex items-center gap-2 mb-4">
            <Info className="h-4 w-4 text-sky-600" />
            <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100">
              About
            </h2>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">App</span>
              <span className="font-medium text-gray-900 dark:text-gray-100">
                4DPocket
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Version</span>
              <span className="font-medium text-gray-900 dark:text-gray-100">
                0.1.0
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
