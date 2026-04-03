import { Link, useLocation } from "react-router-dom";
import { Home, BookOpen, Search, FolderOpen, Tags, FileText, Settings, Menu, X, Share2, Shield, LogOut, User, Rss, Zap, Clock, Highlighter, Star, Archive } from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import { useCurrentUser, useLogout } from "@/hooks/use-auth";

const navItems = [
  { path: "/", label: "Dashboard", icon: Home },
  { path: "/knowledge", label: "Knowledge Base", icon: BookOpen },
  { path: "/knowledge?is_favorite=true", label: "Favorites", icon: Star },
  { path: "/knowledge?is_archived=true", label: "Archive", icon: Archive },
  { path: "/search", label: "Search", icon: Search },
  { path: "/collections", label: "Collections", icon: FolderOpen },
  { path: "/tags", label: "Tags", icon: Tags },
  { path: "/notes", label: "Notes", icon: FileText },
  { path: "/shared", label: "Shared with Me", icon: Share2 },
  { path: "/feed", label: "Feed", icon: Rss },
  { path: "/timeline", label: "Timeline", icon: Clock },
  { path: "/highlights", label: "Highlights", icon: Highlighter },
  { path: "/rules", label: "Rules", icon: Zap },
  { path: "/settings", label: "Settings", icon: Settings },
];

function BellIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-4 h-4 flex-shrink-0" fill="none">
      <circle cx="12" cy="12" r="8" fill="#FCD34D" stroke="#D97706" strokeWidth="1.5"/>
      <line x1="12" y1="12" x2="12" y2="18" stroke="#D97706" strokeWidth="1.5"/>
    </svg>
  );
}

function SidebarLogo() {
  return (
    <svg viewBox="0 0 512 512" className="w-8 h-8 flex-shrink-0">
      <circle cx="256" cy="256" r="240" fill="#0096C7"/>
      <circle cx="256" cy="280" r="160" fill="white"/>
      <path d="M176 300 Q176 380 256 380 Q336 380 336 300" fill="none" stroke="#0096C7" strokeWidth="8" strokeLinecap="round"/>
      <path d="M196 300 Q196 260 256 260 Q316 260 316 300" fill="#F0F9FF" stroke="#0096C7" strokeWidth="4"/>
      <text x="230" y="240" fontFamily="Inter, Arial, sans-serif" fontWeight="900" fontSize="64" fill="#0096C7">4D</text>
      <circle cx="256" cy="340" r="16" fill="#FCD34D" stroke="#D97706" strokeWidth="2"/>
      <line x1="256" y1="340" x2="256" y2="356" stroke="#D97706" strokeWidth="2"/>
      <circle cx="256" cy="196" r="12" fill="#EF4444"/>
    </svg>
  );
}

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
      className={`hidden md:flex flex-col border-r border-sky-100 dark:border-gray-800 bg-white dark:bg-gray-950 transition-all duration-200 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      <div className="flex items-center gap-2 p-4 border-b border-sky-100 dark:border-gray-800 min-h-[60px]">
        <button
          onClick={toggleSidebar}
          className="p-2 rounded-xl hover:bg-sky-50 dark:hover:bg-gray-800 transition-all duration-200 cursor-pointer text-gray-600 dark:text-gray-400 flex-shrink-0 min-w-[44px] min-h-[44px] flex items-center justify-center"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <Menu size={18} /> : <X size={18} />}
        </button>
        {!collapsed && (
          <div className="flex items-center gap-1.5 overflow-hidden">
            <SidebarLogo />
            <div className="flex items-baseline gap-1">
              <span className="font-bold text-lg text-[#0096C7] leading-none">4D</span>
              <span className="font-semibold text-lg text-gray-800 dark:text-gray-100 leading-none">Pocket</span>
            </div>
            <BellIcon />
          </div>
        )}
        {collapsed && (
          <div className="flex items-center justify-center w-full">
            <SidebarLogo />
          </div>
        )}
      </div>

      <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
        {allNavItems.map((item) => {
          const itemPath = item.path.split("?")[0];
          const itemSearch = item.path.includes("?") ? item.path.split("?")[1] : null;
          const specialParams = ["is_favorite", "is_archived"];
          const hasSpecialParam = specialParams.some((p) => location.search.includes(p));
          const isActive =
            itemPath === "/"
              ? location.pathname === "/" && !location.search
              : location.pathname.startsWith(itemPath) &&
                (itemSearch
                  ? location.search.includes(itemSearch)
                  : !hasSpecialParam);
          const Icon = item.icon;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-all duration-200 cursor-pointer min-h-[44px] ${
                isActive
                  ? "bg-sky-50 dark:bg-sky-950 text-[#0096C7] dark:text-sky-400 font-medium"
                  : "text-gray-600 dark:text-gray-400 hover:bg-sky-50/50 dark:hover:bg-gray-800"
              }`}
            >
              <Icon size={18} className="flex-shrink-0" />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t border-sky-100 dark:border-gray-800">
        {user && !collapsed ? (
          <div className="flex items-center gap-3 mb-2 px-1">
            <div className="w-8 h-8 rounded-full bg-sky-100 dark:bg-sky-900 flex items-center justify-center flex-shrink-0">
              <User size={14} className="text-[#0096C7]" />
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
          className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-gray-500 dark:text-gray-400 hover:bg-red-50 dark:hover:bg-red-950/30 hover:text-red-600 dark:hover:text-red-400 transition-all duration-200 cursor-pointer w-full min-h-[44px] ${
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
