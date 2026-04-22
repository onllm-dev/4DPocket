import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Home, BookOpen, Search, FolderOpen, Tags, FileText, Settings, Menu, X, Share2, Shield, LogOut, User, Rss, Zap, Clock, Highlighter, Star, Archive, BookMarked, Network } from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import { useCurrentUser, useLogout } from "@/hooks/use-auth";
import { version } from "../../../package.json";

const navSections = [
  {
    label: "Main",
    items: [
      { path: "/", label: "Dashboard", icon: Home },
      { path: "/knowledge", label: "Knowledge Base", icon: BookOpen },
      { path: "/knowledge?is_favorite=true", label: "Favorites", icon: Star },
      { path: "/knowledge?is_archived=true", label: "Archive", icon: Archive },
      { path: "/search", label: "Search", icon: Search },
    ],
  },
  {
    label: "Organize",
    items: [
      { path: "/collections", label: "Collections", icon: FolderOpen },
      { path: "/tags", label: "Tags", icon: Tags },
      { path: "/notes", label: "Notes", icon: FileText },
      { path: "/reading-list", label: "Reading List", icon: BookMarked },
    ],
  },
  {
    label: "Social",
    items: [
      { path: "/shared", label: "Shared with Me", icon: Share2 },
      { path: "/feed", label: "Feed", icon: Rss },
    ],
  },
  {
    label: "Discover",
    items: [
      { path: "/timeline", label: "Timeline", icon: Clock },
      { path: "/highlights", label: "Highlights", icon: Highlighter },
      { path: "/entities", label: "Knowledge Graph", icon: Network },
    ],
  },
  {
    label: "System",
    items: [
      { path: "/rules", label: "Rules", icon: Zap },
      { path: "/settings", label: "Settings", icon: Settings },
    ],
  },
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
    <img
      src="/icons/icon-192.png"
      alt="4DPocket"
      className="w-8 h-8 flex-shrink-0 rounded-md"
    />
  );
}

export function Sidebar() {
  const location = useLocation();
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const { data: user } = useCurrentUser();
  const logout = useLogout();

  useEffect(() => {
    if (collapsed) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") toggleSidebar();
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [collapsed, toggleSidebar]);

  const allSections = user?.role === "admin"
    ? navSections.map((s) =>
        s.label === "System"
          ? { ...s, items: [{ path: "/admin", label: "Admin", icon: Shield }, ...s.items] }
          : s
      )
    : navSections;

  const isNavActive = (item: { path: string }) => {
    const itemPath = item.path.split("?")[0];
    const itemSearch = item.path.includes("?") ? item.path.split("?")[1] : null;
    const specialParams = ["is_favorite", "is_archived"];
    const hasSpecialParam = specialParams.some((p) => location.search.includes(p));
    return itemPath === "/"
      ? location.pathname === "/" && !location.search
      : location.pathname.startsWith(itemPath) &&
          (itemSearch ? location.search.includes(itemSearch) : !hasSpecialParam);
  };

  return (
    <>
      {/* Mobile overlay backdrop */}
      {!collapsed && (
        <div
          className="md:hidden fixed inset-0 bg-black/50 z-30"
          onClick={toggleSidebar}
          onKeyDown={(e) => { if (e.key === "Escape") toggleSidebar(); }}
          role="button"
          tabIndex={0}
          aria-label="Close sidebar"
        />
      )}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-40 flex flex-col border-r border-sky-100 dark:border-gray-800 bg-white dark:bg-gray-950 transition-all duration-200 ${
          collapsed ? "w-16 -translate-x-full md:translate-x-0" : "w-60 translate-x-0"
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

      <nav aria-label="Main navigation" className="flex-1 p-2 overflow-y-auto">
        {allSections.map((section) => (
          <div key={section.label} className="mb-1">
            {!collapsed && (
              <span className="block px-3 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                {section.label}
              </span>
            )}
            {collapsed && section.label !== "Main" && (
              <div className="mx-3 my-2 border-t border-gray-200 dark:border-gray-800" />
            )}
            {section.items.map((item) => {
              const isActive = isNavActive(item);
              const Icon = item.icon;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-all duration-200 cursor-pointer min-h-[44px] relative ${
                    isActive
                      ? "bg-sky-50 dark:bg-sky-950/60 text-[#0096C7] dark:text-sky-400 font-medium"
                      : "text-gray-600 dark:text-gray-400 hover:bg-sky-50/50 dark:hover:bg-gray-800/50"
                  }`}
                >
                  {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-[#0096C7] dark:bg-sky-400 rounded-r-full" />
                  )}
                  <Icon size={18} className="flex-shrink-0" />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="p-3 border-t border-sky-100 dark:border-gray-800 pb-20 md:pb-0">
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
          onClick={() => logout.mutate()}
          className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-gray-500 dark:text-gray-400 hover:bg-red-50 dark:hover:bg-red-950/30 hover:text-red-600 dark:hover:text-red-400 transition-all duration-200 cursor-pointer w-full min-h-[44px] ${
            collapsed ? "justify-center" : ""
          }`}
        >
          <LogOut size={18} className="flex-shrink-0" />
          {!collapsed && <span>Sign out</span>}
        </button>
        {!collapsed && (
          <span className="block text-[10px] text-gray-400 dark:text-gray-600 px-3 mt-1">v{version}</span>
        )}
      </div>
    </aside>
    </>
  );
}
