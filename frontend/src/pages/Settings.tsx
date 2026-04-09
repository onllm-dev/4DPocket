import { useState, useEffect } from "react";
import { version } from "../../package.json";
import {
  Settings as SettingsIcon,
  Sun,
  Moon,
  Monitor,
  Grid3x3,
  List,
  Info,
  Sparkles,
  Download,
  Share2,
  User,
  Lock,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useUIStore } from "@/stores/ui-store";
import { useCurrentUser, useUpdateProfile, useChangePassword } from "@/hooks/use-auth";

type Theme = "light" | "dark" | "system";
type ViewMode = "grid" | "list";

interface ApiSettings {
  ai_provider: string;
  auto_tag: boolean;
  auto_summarize: boolean;
  tag_confidence_threshold: number;
  media_download: boolean;
  default_share_mode: string;
  theme: string;
  view_mode: string;
}

const THEMES: { value: Theme; label: string; icon: React.ReactNode }[] = [
  { value: "light", label: "Light", icon: <Sun className="h-4 w-4" /> },
  { value: "dark", label: "Dark", icon: <Moon className="h-4 w-4" /> },
  { value: "system", label: "System", icon: <Monitor className="h-4 w-4" /> },
];

const VIEW_MODES: { value: ViewMode; label: string; icon: React.ReactNode }[] = [
  { value: "grid", label: "Grid", icon: <Grid3x3 className="h-4 w-4" /> },
  { value: "list", label: "List", icon: <List className="h-4 w-4" /> },
];

const SHARE_MODES = ["private", "public"];

export default function Settings() {
  const qc = useQueryClient();
  const { theme, viewMode, setTheme, setViewMode } = useUIStore();
  const { data: currentUser } = useCurrentUser();
  const updateProfile = useUpdateProfile();
  const changePassword = useChangePassword();
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [currentPwd, setCurrentPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");

  useEffect(() => {
    if (currentUser) {
      setDisplayName(currentUser.display_name || "");
      setBio(currentUser.bio || "");
    }
  }, [currentUser]);

  const { data: settings } = useQuery<ApiSettings>({
    queryKey: ["settings"],
    queryFn: () => api.get("/api/v1/settings"),
  });

  const updateSettings = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.patch("/api/v1/settings", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  function handleThemeChange(value: Theme) {
    setTheme(value);
    updateSettings.mutate({ theme: value });
  }

  function handleViewModeChange(value: ViewMode) {
    setViewMode(value);
    updateSettings.mutate({ view_mode: value });
  }

  return (
    <div className="animate-fade-in p-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <SettingsIcon className="h-6 w-6 text-sky-600" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Settings
        </h1>
      </div>

      <div className="space-y-6">
        {/* Profile */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5">
          <div className="flex items-center gap-2 mb-4">
            <User className="h-4 w-4 text-sky-600" />
            <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100">Profile</h2>
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Display Name</label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                onBlur={() => { if (displayName !== (currentUser?.display_name || "")) updateProfile.mutate({ display_name: displayName }); }}
                placeholder="Your name"
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-sky-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Bio</label>
              <textarea
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                onBlur={() => { if (bio !== (currentUser?.bio || "")) updateProfile.mutate({ bio }); }}
                placeholder="A short bio..."
                rows={2}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-sky-500 focus:outline-none resize-y"
              />
            </div>
          </div>
        </div>

        {/* Security */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5">
          <div className="flex items-center gap-2 mb-4">
            <Lock className="h-4 w-4 text-sky-600" />
            <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100">Security</h2>
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Current Password</label>
              <input type="password" value={currentPwd} onChange={(e) => setCurrentPwd(e.target.value)} className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-sky-500 focus:outline-none" />
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">New Password</label>
              <input type="password" value={newPwd} onChange={(e) => setNewPwd(e.target.value)} className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-sky-500 focus:outline-none" />
            </div>
            <button
              onClick={() => { changePassword.mutate({ current_password: currentPwd, new_password: newPwd }); setCurrentPwd(""); setNewPwd(""); }}
              disabled={!currentPwd || !newPwd || changePassword.isPending}
              className="px-4 py-2 bg-sky-600 text-white text-sm rounded-lg hover:bg-sky-700 disabled:opacity-50 transition-colors cursor-pointer"
            >
              {changePassword.isPending ? "Changing..." : "Change Password"}
            </button>
            {changePassword.isError && <p className="text-xs text-red-500">Failed to change password</p>}
            {changePassword.isSuccess && <p className="text-xs text-green-500">Password changed successfully</p>}
          </div>
        </div>

        {/* Appearance */}
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
                  onClick={() => handleThemeChange(t.value)}
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
                  onClick={() => handleViewModeChange(m.value)}
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

        {/* AI Settings */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="h-4 w-4 text-sky-600" />
            <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100">
              AI Settings
            </h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm text-gray-900 dark:text-gray-100 font-medium">
                  Auto-tag
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
                  Automatically tag new items with AI
                </p>
              </div>
              <button
                role="switch"
                aria-checked={settings?.auto_tag ?? false}
                onClick={() =>
                  updateSettings.mutate({ auto_tag: !(settings?.auto_tag) })
                }
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 cursor-pointer ${
                  settings?.auto_tag
                    ? "bg-sky-600"
                    : "bg-gray-200 dark:bg-gray-700"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                    settings?.auto_tag ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between py-2 border-t border-gray-100 dark:border-gray-800">
              <div>
                <p className="text-sm text-gray-900 dark:text-gray-100 font-medium">
                  Auto-summarize
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
                  Generate summaries for new items
                </p>
              </div>
              <button
                role="switch"
                aria-checked={settings?.auto_summarize ?? false}
                onClick={() =>
                  updateSettings.mutate({
                    auto_summarize: !(settings?.auto_summarize),
                  })
                }
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 cursor-pointer ${
                  settings?.auto_summarize
                    ? "bg-sky-600"
                    : "bg-gray-200 dark:bg-gray-700"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                    settings?.auto_summarize ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>

            <div className="py-2 border-t border-gray-100 dark:border-gray-800">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="text-sm text-gray-900 dark:text-gray-100 font-medium">
                    Tag confidence threshold
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
                    Minimum confidence to apply a tag
                  </p>
                </div>
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {Math.round((settings?.tag_confidence_threshold ?? 0.7) * 100)}%
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={settings?.tag_confidence_threshold ?? 0.7}
                onChange={(e) =>
                  updateSettings.mutate({
                    tag_confidence_threshold: parseFloat(e.target.value),
                  })
                }
                className="w-full accent-sky-600 cursor-pointer"
              />
            </div>
          </div>
        </div>

        {/* Media */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5">
          <div className="flex items-center gap-2 mb-4">
            <Download className="h-4 w-4 text-sky-600" />
            <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100">
              Media
            </h2>
          </div>

          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-sm text-gray-900 dark:text-gray-100 font-medium">
                Download media
              </p>
              <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
                Save images and videos locally
              </p>
            </div>
            <button
              role="switch"
              aria-checked={settings?.media_download ?? false}
              onClick={() =>
                updateSettings.mutate({
                  media_download: !(settings?.media_download),
                })
              }
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 cursor-pointer ${
                settings?.media_download
                  ? "bg-sky-600"
                  : "bg-gray-200 dark:bg-gray-700"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                  settings?.media_download ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </div>

        {/* Sharing */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5">
          <div className="flex items-center gap-2 mb-4">
            <Share2 className="h-4 w-4 text-sky-600" />
            <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100">
              Sharing
            </h2>
          </div>

          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-sm text-gray-900 dark:text-gray-100 font-medium">
                Default share mode
              </p>
              <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
                Default visibility for shared items
              </p>
            </div>
            <select
              value={settings?.default_share_mode ?? "private"}
              onChange={(e) =>
                updateSettings.mutate({ default_share_mode: e.target.value })
              }
              className="text-sm bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5 rounded-lg border-none outline-none cursor-pointer"
            >
              {SHARE_MODES.map((m) => (
                <option key={m} value={m}>
                  {m.charAt(0).toUpperCase() + m.slice(1)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* About */}
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
                {version}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
