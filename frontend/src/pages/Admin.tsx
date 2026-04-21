import { Shield, Users, Settings as SettingsIcon, Loader2, UserX, UserCheck, ShieldX, Sparkles, Eye, EyeOff, Activity, Database, HardDrive, Tag as TagIcon, FolderOpen, FileText, Users as UsersIcon } from "lucide-react";
import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { timeAgo } from "@/lib/utils";
import { useCurrentUser } from "@/hooks/use-auth";

interface AdminUser {
  id: string;
  username: string;
  email: string;
  display_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface InstanceSettingsData {
  instance_name: string;
  registration_enabled: boolean;
  registration_mode: string;
  default_user_role: string;
  max_users: number | null;
}

interface AIConfig {
  chat_provider: string;
  ollama_url: string;
  ollama_model: string;
  groq_api_key: string;
  nvidia_api_key: string;
  custom_base_url: string;
  custom_api_key: string;
  custom_model: string;
  custom_api_type: string;
  embedding_provider: string;
  auto_tag: boolean;
  auto_summarize: boolean;
  tag_confidence_threshold: number;
  sync_enrichment: boolean;
}

interface SearchConfig {
  graph_ranker_enabled: boolean;
  graph_ranker_hop_decay: number;
  graph_ranker_top_k: number;
}

export default function Admin() {
  const navigate = useNavigate();
  const { data: currentUser } = useCurrentUser();

  // All hooks called unconditionally before any returns (React rules of hooks)
  const qc = useQueryClient();
  const { data: users, isLoading: usersLoading } = useQuery<AdminUser[]>({
    queryKey: ["admin", "users"],
    queryFn: () => api.get("/api/v1/admin/users"),
    enabled: !!currentUser && currentUser.role === "admin",
  });

  const { data: settings, isLoading: settingsLoading } = useQuery<InstanceSettingsData>({
    queryKey: ["admin", "settings"],
    queryFn: () => api.get("/api/v1/admin/settings"),
    enabled: !!currentUser && currentUser.role === "admin",
  });

  const updateSettings = useMutation({
    mutationFn: (data: Partial<InstanceSettingsData>) =>
      api.patch("/api/v1/admin/settings", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "settings"] }),
  });

  const updateUser = useMutation({
    mutationFn: ({ id, ...data }: { id: string; role?: string; is_active?: boolean }) =>
      api.patch(`/api/v1/admin/users/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  });

  const { data: aiConfig } = useQuery<AIConfig>({
    queryKey: ["admin", "ai-settings"],
    queryFn: () => api.get("/api/v1/admin/ai-settings"),
    enabled: !!currentUser && currentUser.role === "admin",
  });

  interface InstanceStats {
    users_total: number;
    users_active: number;
    items_total: number;
    collections_total: number;
    tags_total: number;
    entities_total: number;
    storage_bytes: number;
    queue_depth: number;
    worker_alive: boolean;
  }

  const { data: stats, isLoading: statsLoading } = useQuery<InstanceStats>({
    queryKey: ["admin", "stats"],
    queryFn: () => api.get("/api/v1/admin/stats"),
    enabled: !!currentUser && currentUser.role === "admin",
    refetchInterval: 30000,
  });

  const updateAI = useMutation({
    mutationFn: (data: Partial<AIConfig>) =>
      api.patch("/api/v1/admin/ai-settings", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "ai-settings"] }),
  });

  const { data: searchConfig } = useQuery<SearchConfig>({
    queryKey: ["admin", "search-settings"],
    queryFn: () => api.get("/api/v1/admin/search-settings"),
    enabled: !!currentUser && currentUser.role === "admin",
  });

  const updateSearch = useMutation({
    mutationFn: (data: Partial<SearchConfig>) =>
      api.patch("/api/v1/admin/search-settings", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "search-settings"] }),
  });

  // Role guard: redirect non-admins
  if (currentUser && currentUser.role !== "admin") {
    return (
      <div className="animate-fade-in max-w-5xl mx-auto px-4 md:px-6 py-16 text-center">
        <div className="flex flex-col items-center gap-4">
          <ShieldX className="w-16 h-16 text-red-400" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Access Denied</h1>
          <p className="text-gray-500 dark:text-gray-400">
            You need admin privileges to access this page.
          </p>
          <button
            onClick={() => navigate("/")}
            className="mt-2 px-4 py-2 bg-sky-600 text-white rounded-lg text-sm font-medium hover:bg-sky-700 cursor-pointer"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in max-w-5xl mx-auto px-4 md:px-6">
      <div className="flex items-center gap-3 mb-6">
        <Shield className="w-6 h-6 text-sky-600" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Admin Panel</h1>
      </div>

      {/* Analytics */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-6 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-5 h-5 text-sky-600" />
          <h2 className="font-bold text-gray-900 dark:text-gray-100">Analytics</h2>
          {statsLoading && <Loader2 className="w-3 h-3 animate-spin text-gray-400" />}
        </div>
        {stats ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard icon={<UsersIcon className="w-4 h-4" />} label="Users" value={`${stats.users_active}/${stats.users_total}`} hint="active / total" />
            <StatCard icon={<Database className="w-4 h-4" />} label="Items" value={stats.items_total.toLocaleString()} />
            <StatCard icon={<FolderOpen className="w-4 h-4" />} label="Collections" value={stats.collections_total.toLocaleString()} />
            <StatCard icon={<TagIcon className="w-4 h-4" />} label="Tags" value={stats.tags_total.toLocaleString()} />
            <StatCard icon={<FileText className="w-4 h-4" />} label="Entities" value={stats.entities_total.toLocaleString()} />
            <StatCard icon={<HardDrive className="w-4 h-4" />} label="Storage" value={formatBytes(stats.storage_bytes)} hint="data/ on disk" />
            <StatCard
              icon={<Activity className={`w-4 h-4 ${stats.worker_alive ? "text-green-500" : "text-red-500"}`} />}
              label="Worker"
              value={stats.worker_alive ? "Running" : "Stopped"}
              hint={stats.worker_alive ? undefined : "No Huey processes detected"}
            />
            <StatCard icon={<Database className="w-4 h-4" />} label="Queue" value={stats.queue_depth.toString()} hint="pending tasks" />
          </div>
        ) : statsLoading ? (
          <div className="flex items-center gap-2 text-gray-400"><Loader2 className="w-4 h-4 animate-spin" /> Loading stats...</div>
        ) : (
          <p className="text-sm text-gray-500 dark:text-gray-400">Stats unavailable.</p>
        )}
      </div>

      {/* Instance Settings */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-6 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <SettingsIcon className="w-5 h-5 text-sky-600" />
          <h2 className="font-bold text-gray-900 dark:text-gray-100">Instance Settings</h2>
        </div>
        {settingsLoading ? (
          <div className="flex items-center gap-2 text-gray-400"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>
        ) : settings ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Registration</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">Allow new users to register</p>
              </div>
              <button
                onClick={() => updateSettings.mutate({ registration_enabled: !settings.registration_enabled })}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer ${
                  settings.registration_enabled
                    ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
                    : "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400"
                }`}
              >
                {settings.registration_enabled ? "Enabled" : "Disabled"}
              </button>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Registration Mode</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">open / invite / disabled</p>
              </div>
              <div className="flex gap-1">
                {["open", "invite", "disabled"].map((mode) => (
                  <button
                    key={mode}
                    onClick={() => updateSettings.mutate({ registration_mode: mode })}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                      settings.registration_mode === mode
                        ? "bg-sky-600 text-white"
                        : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
                    }`}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Instance Name</p>
              </div>
              <span className="text-sm text-gray-600 dark:text-gray-400">{settings.instance_name}</span>
            </div>
          </div>
        ) : null}
      </div>

      {/* AI Configuration */}
      <AIConfigSection config={aiConfig} onUpdate={(data) => updateAI.mutate(data)} />

      {/* Search Configuration */}
      <SearchConfigSection config={searchConfig} onUpdate={(data) => updateSearch.mutate(data)} />

      {/* Users Table */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-6">
        <div className="flex items-center gap-2 mb-4">
          <Users className="w-5 h-5 text-sky-600" />
          <h2 className="font-bold text-gray-900 dark:text-gray-100">Users ({users?.length || 0})</h2>
        </div>
        {usersLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 animate-pulse bg-gray-100 dark:bg-gray-800 rounded-lg" />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {users?.map((user) => (
              <div
                key={user.id}
                className="flex items-center gap-4 p-3 rounded-lg border border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-all"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-gray-900 dark:text-gray-100">{user.display_name || user.username}</span>
                    <span className="text-xs text-gray-400">@{user.username}</span>
                    {user.role === "admin" && (
                      <span className="text-[10px] bg-sky-100 dark:bg-sky-900/30 text-sky-600 px-1.5 py-0.5 rounded font-medium">ADMIN</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500">{user.email} · Joined {timeAgo(user.created_at)}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => updateUser.mutate({ id: user.id, is_active: !user.is_active })}
                    className={`p-2 rounded-lg transition-all cursor-pointer ${
                      user.is_active
                        ? "text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20"
                        : "text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                    }`}
                    title={user.is_active ? "Deactivate" : "Activate"}
                  >
                    {user.is_active ? <UserCheck className="w-4 h-4" /> : <UserX className="w-4 h-4" />}
                  </button>
                  <select
                    value={user.role}
                    onChange={(e) => updateUser.mutate({ id: user.id, role: e.target.value })}
                    className="text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-2 py-1.5 cursor-pointer"
                  >
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                    <option value="guest">Guest</option>
                  </select>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function StatCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30 p-3">
      <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 mb-1">
        {icon}
        <span>{label}</span>
      </div>
      <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{value}</div>
      {hint && <div className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">{hint}</div>}
    </div>
  );
}

const PROVIDERS = [
  { value: "ollama", label: "Ollama (Local)" },
  { value: "groq", label: "Groq (Cloud)" },
  { value: "nvidia", label: "NVIDIA (Cloud)" },
  { value: "custom", label: "Custom Endpoint" },
];

const API_TYPES = [
  { value: "openai", label: "OpenAI-compatible" },
  { value: "anthropic", label: "Anthropic-compatible" },
];

function AIConfigSection({ config, onUpdate }: { config?: AIConfig; onUpdate: (data: Partial<AIConfig>) => void }) {
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [localConfig, setLocalConfig] = useState<AIConfig | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  // Sync local config from server config on load
  const prevConfig = useRef(config);
  if (config && !localConfig && config !== prevConfig.current) {
    prevConfig.current = config;
  }
  if (config && !localConfig) {
    setLocalConfig({ ...config });
  }

  if (!config) return null;
  const effective = localConfig || config;

  const toggleKey = (key: string) => setShowKeys((prev) => ({ ...prev, [key]: !prev[key] }));

  const updateLocal = (data: Partial<AIConfig>) => {
    setLocalConfig((prev) => prev ? { ...prev, ...data } : { ...config, ...data });
    setHasChanges(true);
  };

  const handleSave = () => {
    if (localConfig) {
      onUpdate(localConfig);
      setHasChanges(false);
    }
  };

  const handleDiscard = () => {
    setLocalConfig({ ...config });
    setHasChanges(false);
  };

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-sky-600" />
          <h2 className="font-bold text-gray-900 dark:text-gray-100">AI Configuration</h2>
        </div>
        {hasChanges && (
          <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">Unsaved changes</span>
        )}
      </div>

      <div className="space-y-4">
        {/* Provider Selection */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Chat Provider</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">AI model provider for tagging and summarization</p>
          </div>
          <select
            value={effective.chat_provider}
            onChange={(e) => updateLocal({ chat_provider: e.target.value })}
            className="text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5 cursor-pointer"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>

        {/* Ollama Settings */}
        {effective.chat_provider === "ollama" && (
          <div className="space-y-3 pl-4 border-l-2 border-sky-200 dark:border-sky-800">
            <div>
              <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Ollama URL</label>
              <input
                type="text"
                value={effective.ollama_url || ""}
                onChange={(e) => updateLocal({ ollama_url: e.target.value })}
                className="w-full mt-1 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Model</label>
              <input
                type="text"
                value={effective.ollama_model || ""}
                onChange={(e) => updateLocal({ ollama_model: e.target.value })}
                className="w-full mt-1 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5"
              />
            </div>
          </div>
        )}

        {/* Groq Settings */}
        {effective.chat_provider === "groq" && (
          <div className="pl-4 border-l-2 border-sky-200 dark:border-sky-800">
            <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Groq API Key</label>
            <div className="relative mt-1">
              <input
                type={showKeys.groq ? "text" : "password"}
                value={effective.groq_api_key || ""}
                onChange={(e) => updateLocal({ groq_api_key: e.target.value })}
                placeholder="gsk_..."
                className="w-full text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5 pr-10"
              />
              <button onClick={() => toggleKey("groq")} className="absolute right-2 top-1.5 text-gray-400 cursor-pointer">
                {showKeys.groq ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
        )}

        {/* NVIDIA Settings */}
        {effective.chat_provider === "nvidia" && (
          <div className="pl-4 border-l-2 border-sky-200 dark:border-sky-800">
            <label className="text-xs font-medium text-gray-600 dark:text-gray-400">NVIDIA API Key</label>
            <div className="relative mt-1">
              <input
                type={showKeys.nvidia ? "text" : "password"}
                value={effective.nvidia_api_key || ""}
                onChange={(e) => updateLocal({ nvidia_api_key: e.target.value })}
                placeholder="nvapi-..."
                className="w-full text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5 pr-10"
              />
              <button onClick={() => toggleKey("nvidia")} className="absolute right-2 top-1.5 text-gray-400 cursor-pointer">
                {showKeys.nvidia ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
        )}

        {/* Custom Provider Settings */}
        {effective.chat_provider === "custom" && (
          <div className="space-y-3 pl-4 border-l-2 border-sky-200 dark:border-sky-800">
            <div>
              <label className="text-xs font-medium text-gray-600 dark:text-gray-400">API Type</label>
              <select
                value={effective.custom_api_type || "openai"}
                onChange={(e) => updateLocal({ custom_api_type: e.target.value })}
                className="w-full mt-1 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5 cursor-pointer"
              >
                {API_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Base URL</label>
              <input
                type="text"
                value={effective.custom_base_url || ""}
                onChange={(e) => updateLocal({ custom_base_url: e.target.value })}
                placeholder="https://api.minimax.io/anthropic/v1"
                className="w-full mt-1 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 dark:text-gray-400">API Key</label>
              <div className="relative mt-1">
                <input
                  type={showKeys.custom ? "text" : "password"}
                  value={effective.custom_api_key || ""}
                  onChange={(e) => updateLocal({ custom_api_key: e.target.value })}
                  placeholder="sk-..."
                  className="w-full text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5 pr-10"
                />
                <button onClick={() => toggleKey("custom")} className="absolute right-2 top-1.5 text-gray-400 cursor-pointer">
                  {showKeys.custom ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Model Name</label>
              <input
                type="text"
                value={effective.custom_model || ""}
                onChange={(e) => updateLocal({ custom_model: e.target.value })}
                placeholder="MiniMax-M2.7"
                className="w-full mt-1 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5"
              />
            </div>
          </div>
        )}

        {/* Divider */}
        <div className="border-t border-gray-100 dark:border-gray-800 pt-4">
          <p className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3">AI Features</p>
        </div>

        {/* Auto-tag */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Auto-tag</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Automatically tag items with AI</p>
          </div>
          <button
            onClick={() => updateLocal({ auto_tag: !effective.auto_tag })}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 cursor-pointer ${
              effective.auto_tag ? "bg-sky-600" : "bg-gray-200 dark:bg-gray-700"
            }`}
          >
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
              effective.auto_tag ? "translate-x-6" : "translate-x-1"
            }`} />
          </button>
        </div>

        {/* Auto-summarize */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Auto-summarize</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Generate summaries for new items</p>
          </div>
          <button
            onClick={() => updateLocal({ auto_summarize: !effective.auto_summarize })}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 cursor-pointer ${
              effective.auto_summarize ? "bg-sky-600" : "bg-gray-200 dark:bg-gray-700"
            }`}
          >
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
              effective.auto_summarize ? "translate-x-6" : "translate-x-1"
            }`} />
          </button>
        </div>

        {/* Sync enrichment */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Sync Enrichment</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Run AI inline when background worker is not running</p>
          </div>
          <button
            onClick={() => updateLocal({ sync_enrichment: !effective.sync_enrichment })}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 cursor-pointer ${
              effective.sync_enrichment ? "bg-sky-600" : "bg-gray-200 dark:bg-gray-700"
            }`}
          >
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
              effective.sync_enrichment ? "translate-x-6" : "translate-x-1"
            }`} />
          </button>
        </div>

        {/* Embedding Provider */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Embedding Provider</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Vector embeddings for semantic search</p>
          </div>
          <select
            value={effective.embedding_provider}
            onChange={(e) => updateLocal({ embedding_provider: e.target.value })}
            className="text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5 cursor-pointer"
          >
            <option value="local">Local (sentence-transformers)</option>
            <option value="nvidia">NVIDIA</option>
          </select>
        </div>

        {/* Save / Discard buttons */}
        <div className="flex items-center gap-3 pt-4 border-t border-gray-100 dark:border-gray-800">
          <button
            onClick={handleSave}
            disabled={!hasChanges}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
              hasChanges
                ? "bg-sky-600 hover:bg-sky-700 text-white shadow-sm"
                : "bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed"
            }`}
          >
            Save Changes
          </button>
          {hasChanges && (
            <button
              onClick={handleDiscard}
              className="px-5 py-2 rounded-lg text-sm font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              Discard
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function SearchConfigSection({ config, onUpdate }: { config?: SearchConfig; onUpdate: (data: Partial<SearchConfig>) => void }) {
  const [localConfig, setLocalConfig] = useState<SearchConfig | null>(null);
  const effective = localConfig ?? config;
  const isDirty = localConfig !== null && JSON.stringify(localConfig) !== JSON.stringify(config);

  const updateLocal = (patch: Partial<SearchConfig>) => {
    setLocalConfig({ ...(effective as SearchConfig), ...patch });
  };

  const handleSave = () => {
    if (!localConfig || !config) return;
    const changed: Partial<SearchConfig> = {};
    (Object.keys(localConfig) as (keyof SearchConfig)[]).forEach((k) => {
      if (localConfig[k] !== config[k]) {
        (changed as Record<string, unknown>)[k] = localConfig[k];
      }
    });
    if (Object.keys(changed).length > 0) {
      onUpdate(changed);
      setLocalConfig(null);
    }
  };

  if (!effective) {
    return (
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-6">
        <div className="flex items-center gap-2 mb-4">
          <SettingsIcon className="w-5 h-5 text-sky-600" />
          <h2 className="font-bold text-gray-900 dark:text-gray-100">Search Configuration</h2>
        </div>
        <div className="h-24 animate-pulse bg-gray-100 dark:bg-gray-800 rounded-lg" />
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-4">
        <SettingsIcon className="w-5 h-5 text-sky-600" />
        <h2 className="font-bold text-gray-900 dark:text-gray-100">Search Configuration</h2>
        <span className="ml-auto text-xs text-gray-500 dark:text-gray-400">Admin overrides .env</span>
      </div>

      <div className="space-y-4">
        {/* Section header */}
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3">Graph-Anchored Ranker</p>
        </div>

        {/* Enable toggle */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Enable graph ranker</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Rank items by matching entities and 1-hop relations alongside keyword and vector search.
              No-op until entity extraction has populated the concept graph.
            </p>
          </div>
          <button
            onClick={() => updateLocal({ graph_ranker_enabled: !effective.graph_ranker_enabled })}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 cursor-pointer ${
              effective.graph_ranker_enabled ? "bg-sky-600" : "bg-gray-200 dark:bg-gray-700"
            }`}
          >
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
              effective.graph_ranker_enabled ? "translate-x-6" : "translate-x-1"
            }`} />
          </button>
        </div>

        {/* Hop decay */}
        <div className="flex items-center justify-between">
          <div className="flex-1 pr-4">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Hop decay</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Neighbor contribution multiplier (0.0 = seeds only, 1.0 = neighbors fully weighted)
            </p>
          </div>
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={effective.graph_ranker_hop_decay}
            onChange={(e) => updateLocal({ graph_ranker_hop_decay: parseFloat(e.target.value) })}
            className="w-24 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5"
          />
        </div>

        {/* Top k */}
        <div className="flex items-center justify-between">
          <div className="flex-1 pr-4">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Top K</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Max items returned by the graph ranker before fusion</p>
          </div>
          <input
            type="number"
            min={1}
            max={500}
            step={10}
            value={effective.graph_ranker_top_k}
            onChange={(e) => updateLocal({ graph_ranker_top_k: parseInt(e.target.value, 10) })}
            className="w-24 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5"
          />
        </div>

        {/* Save / Discard */}
        <div className="flex justify-end gap-2 pt-4 border-t border-gray-100 dark:border-gray-800">
          <button
            onClick={handleSave}
            disabled={!isDirty}
            className={`px-4 py-2 text-sm font-medium rounded-lg ${
              isDirty
                ? "bg-sky-600 text-white hover:bg-sky-700 cursor-pointer"
                : "bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed"
            }`}
          >
            Save
          </button>
          {isDirty && (
            <button
              onClick={() => setLocalConfig(null)}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 cursor-pointer"
            >
              Discard
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
