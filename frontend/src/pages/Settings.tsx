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
  AlertTriangle,
  Trash2,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useUIStore } from "@/stores/ui-store";
import {
  useCurrentUser,
  useUpdateProfile,
  useChangePassword,
  useDeleteAccount,
  useLogout,
} from "@/hooks/use-auth";
import { ApiTokensSection } from "@/components/settings/ApiTokensSection";
import { McpSetupPanel } from "@/components/settings/McpSetupPanel";

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
  const deleteAccount = useDeleteAccount();
  const logout = useLogout();
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [profileDirty, setProfileDirty] = useState(false);
  const [currentPwd, setCurrentPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deletePassword, setDeletePassword] = useState("");
  const [showDeleteForm, setShowDeleteForm] = useState(false);
  const [tagThreshold, setTagThreshold] = useState<number | null>(null);

  useEffect(() => {
    if (currentUser) {
      setDisplayName(currentUser.display_name || "");
      setBio(currentUser.bio || "");
      setUsername(currentUser.username || "");
      setEmail(currentUser.email || "");
      setProfileDirty(false);
    }
  }, [currentUser]);

  function handleSaveProfile() {
    updateProfile.mutate(
      { username, email, display_name: displayName, bio },
      { onSuccess: () => setProfileDirty(false) }
    );
  }

  function handlePasswordChange() {
    setPasswordError("");
    if (newPwd !== confirmPwd) {
      setPasswordError("New passwords do not match.");
      return;
    }
    if (newPwd.length < 8) {
      setPasswordError("New password must be at least 8 characters.");
      return;
    }
    changePassword.mutate(
      { current_password: currentPwd, new_password: newPwd },
      {
        onSuccess: () => {
          setCurrentPwd("");
          setNewPwd("");
          setConfirmPwd("");
        },
        onError: (err) => {
          setPasswordError(err instanceof Error ? err.message : "Failed to change password");
        },
      }
    );
  }

  function handleDeleteAccount() {
    if (deleteConfirm !== "DELETE") return;
    if (!deletePassword) return;
    deleteAccount.mutate(
      { current_password: deletePassword },
      {
        onSuccess: () => {
          logout.mutate();
        },
      },
    );
  }

  const { data: settings } = useQuery<ApiSettings>({
    queryKey: ["settings"],
    queryFn: () => api.get("/api/v1/settings"),
  });

  const updateSettings = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.patch("/api/v1/settings", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  useEffect(() => {
    if (tagThreshold === null) return;
    const timer = setTimeout(() => {
      updateSettings.mutate({ tag_confidence_threshold: tagThreshold });
    }, 500);
    return () => clearTimeout(timer);
  }, [tagThreshold, updateSettings]);

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
              <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => { setUsername(e.target.value); setProfileDirty(true); }}
                placeholder="username"
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-sky-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setProfileDirty(true); }}
                placeholder="you@example.com"
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-sky-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Display Name</label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => { setDisplayName(e.target.value); setProfileDirty(true); }}
                placeholder="Your name"
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-sky-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Bio</label>
              <textarea
                value={bio}
                onChange={(e) => { setBio(e.target.value); setProfileDirty(true); }}
                placeholder="A short bio..."
                rows={2}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-sky-500 focus:outline-none resize-y"
              />
            </div>
            <button
              onClick={handleSaveProfile}
              disabled={!profileDirty || updateProfile.isPending}
              className="px-4 py-2 bg-sky-600 text-white text-sm rounded-lg hover:bg-sky-700 disabled:opacity-50 transition-colors cursor-pointer"
            >
              {updateProfile.isPending ? "Saving..." : "Save profile"}
            </button>
            {updateProfile.isError && (
              <p className="text-xs text-red-500">
                {updateProfile.error instanceof Error ? updateProfile.error.message : "Failed to save profile"}
              </p>
            )}
            {!updateProfile.isError && updateProfile.isSuccess && !profileDirty && (
              <p className="text-xs text-green-500">Profile saved</p>
            )}
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
              <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-1">
                At least 8 characters with an uppercase letter, a digit, and a special character.
              </p>
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Confirm New Password</label>
              <input
                type="password"
                value={confirmPwd}
                onChange={(e) => setConfirmPwd(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-sky-500 focus:outline-none"
              />
            </div>
            <button
              onClick={handlePasswordChange}
              disabled={!currentPwd || !newPwd || !confirmPwd || changePassword.isPending}
              className="px-4 py-2 bg-sky-600 text-white text-sm rounded-lg hover:bg-sky-700 disabled:opacity-50 transition-colors cursor-pointer"
            >
              {changePassword.isPending ? "Changing..." : "Change Password"}
            </button>
            {passwordError && <p className="text-xs text-red-500">{passwordError}</p>}
            {!passwordError && changePassword.isSuccess && (
              <p className="text-xs text-green-500">Password changed successfully</p>
            )}
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
                value={tagThreshold ?? settings?.tag_confidence_threshold ?? 0.7}
                onChange={(e) => setTagThreshold(parseFloat(e.target.value))}
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

        {/* API Tokens & MCP */}
        <ApiTokensSection />

        {/* MCP reference panel (no token embedded — user pastes theirs) */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5">
          <McpSetupPanel token={null} />
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

        {/* Danger Zone */}
        <div className="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50/40 dark:bg-red-950/20 p-5">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400" />
            <h2 className="text-sm font-bold text-red-700 dark:text-red-300">
              Danger Zone
            </h2>
          </div>
          <p className="text-xs text-red-600/80 dark:text-red-400/80 mb-4">
            Permanently delete your account and all saved items, collections, tokens, and data. This cannot be undone.
          </p>
          {!showDeleteForm ? (
            <button
              onClick={() => setShowDeleteForm(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-gray-900 border border-red-300 dark:border-red-800 text-red-600 dark:text-red-400 text-sm rounded-lg hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors cursor-pointer"
            >
              <Trash2 className="h-4 w-4" />
              Delete my account
            </button>
          ) : (
            <div className="space-y-3">
              <label className="block text-xs text-red-700 dark:text-red-300">
                Type <span className="font-mono font-bold">DELETE</span> to confirm
              </label>
              <input
                type="text"
                value={deleteConfirm}
                onChange={(e) => setDeleteConfirm(e.target.value)}
                placeholder="DELETE"
                className="w-full px-3 py-2 rounded-lg border border-red-200 dark:border-red-800 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-red-500 focus:outline-none"
              />
              <label className="block text-xs text-red-700 dark:text-red-300">
                Re-enter your password
              </label>
              <input
                type="password"
                value={deletePassword}
                onChange={(e) => setDeletePassword(e.target.value)}
                placeholder="Current password"
                autoComplete="current-password"
                className="w-full px-3 py-2 rounded-lg border border-red-200 dark:border-red-800 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-red-500 focus:outline-none"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleDeleteAccount}
                  disabled={deleteConfirm !== "DELETE" || !deletePassword || deleteAccount.isPending}
                  className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors cursor-pointer"
                >
                  {deleteAccount.isPending ? "Deleting..." : "Permanently delete account"}
                </button>
                <button
                  onClick={() => { setShowDeleteForm(false); setDeleteConfirm(""); setDeletePassword(""); }}
                  className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 text-sm rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
              </div>
              {deleteAccount.isError && (
                <p className="text-xs text-red-500">
                  {deleteAccount.error instanceof Error ? deleteAccount.error.message : "Failed to delete account"}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
