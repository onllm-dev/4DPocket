import { Link, useLocation } from "react-router-dom";
import { Home, BookOpen, Search, FolderOpen, Tags, FileText, Settings, Menu, X, Share2, Shield, LogOut, User, Rss } from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import { useCurrentUser, useLogout } from "@/hooks/use-auth";

const navItems = [
  { path: "/", label: "Dashboard", icon: Home },
  { path: "/knowledge", label: "Knowledge Base", icon: BookOpen },
  { path: "/search", label: "Search", icon: Search },
  { path: "/collections", label: "Collections", icon: FolderOpen },
  { path: "/tags", label: "Tags", icon: Tags },
  { path: "/notes", label: "Notes", icon: FileText },
  { path: "/shared", label: "Shared with Me", icon: Share2 },
  { path: "/feed", label: "Feed", icon: Rss },
  { path: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const location = useLocation();
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const { data: user } = useCurrentUser();
  const logout = useLogout();

  const allNavItems = user?.role === "admin"
    ? [...navItems, { path: "/admin", label: "Admin", icon: Shield }]
    : navItems;

  return (
    <aside
      className={`hidden md:flex flex-col border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 transition-all duration-200 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      <div className="flex items-center gap-2 p-4 border-b border-gray-200 dark:border-gray-800 min-h-[60px]">
        <button
          onClick={toggleSidebar}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-all duration-200 cursor-pointer text-gray-600 dark:text-gray-400 flex-shrink-0 min-w-[44px] min-h-[44px] flex items-center justify-center"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <Menu size={18} /> : <X size={18} />}
        </button>
        {!collapsed && (
          <div className="flex items-baseline gap-1 overflow-hidden">
            <span className="font-bold text-lg text-sky-600 leading-none">4D</span>
            <span className="font-semibold text-lg text-gray-800 dark:text-gray-100 leading-none">Pocket</span>
          </div>
        )}
      </div>

      <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
        {allNavItems.map((item) => {
          const isActive =
            item.path === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(item.path);
          const Icon = item.icon;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-200 cursor-pointer min-h-[44px] ${
                isActive
                  ? "bg-sky-50 dark:bg-sky-950 text-sky-600 dark:text-sky-400 font-medium"
                  : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
              }`}
            >
              <Icon size={18} className="flex-shrink-0" />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t border-gray-200 dark:border-gray-800">
        {user && !collapsed ? (
          <div className="flex items-center gap-3 mb-2 px-1">
            <div className="w-8 h-8 rounded-full bg-sky-100 dark:bg-sky-900 flex items-center justify-center flex-shrink-0">
              <User size={14} className="text-sky-600" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                {user.display_name || user.username}
              </p>
              <p className="text-[10px] text-gray-400 truncate">@{user.username}</p>
            </div>
          </div>
        ) : null}
        <button
          onClick={logout}
          className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-500 dark:text-gray-400 hover:bg-red-50 dark:hover:bg-red-950/30 hover:text-red-600 dark:hover:text-red-400 transition-all duration-200 cursor-pointer w-full min-h-[44px] ${
            collapsed ? "justify-center" : ""
          }`}
        >
          <LogOut size={18} className="flex-shrink-0" />
          {!collapsed && <span>Sign out</span>}
        </button>
        {!collapsed && (
          <span className="block text-[10px] text-gray-400 dark:text-gray-600 px-3 mt-1">v0.1.0</span>
        )}
      </div>
    </aside>
  );
}
