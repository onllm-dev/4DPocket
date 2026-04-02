import { Shield, Users, Settings as SettingsIcon, Loader2, UserX, UserCheck } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { timeAgo } from "@/lib/utils";

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

export default function Admin() {
  const qc = useQueryClient();
  const { data: users, isLoading: usersLoading } = useQuery<AdminUser[]>({
    queryKey: ["admin", "users"],
    queryFn: () => api.get("/api/v1/admin/users"),
  });

  const { data: settings, isLoading: settingsLoading } = useQuery<InstanceSettingsData>({
    queryKey: ["admin", "settings"],
    queryFn: () => api.get("/api/v1/admin/settings"),
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

  return (
    <div className="animate-fade-in max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Shield className="w-6 h-6 text-sky-600" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Admin Panel</h1>
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
                <p className="text-xs text-gray-500">Allow new users to register</p>
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
                <p className="text-xs text-gray-500">open / invite / disabled</p>
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
                    className="text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-2 py-1.5 cursor-pointer"
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
