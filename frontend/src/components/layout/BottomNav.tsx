import { Link, useLocation } from "react-router-dom";
import { Home, BookOpen, Search, Rss, Settings } from "lucide-react";

const navItems = [
  { path: "/", label: "Home", icon: Home },
  { path: "/knowledge", label: "Library", icon: BookOpen },
  { path: "/search", label: "Search", icon: Search },
  { path: "/feed", label: "Feed", icon: Rss },
  { path: "/settings", label: "Settings", icon: Settings },
];

export function BottomNav() {
  const location = useLocation();

  return (
    <nav
      aria-label="Mobile navigation"
      className="md:hidden fixed bottom-0 left-0 right-0 bg-white/95 dark:bg-gray-950/95 backdrop-blur-md border-t border-gray-200 dark:border-gray-800 z-50 pb-safe"
    >
      <div className="flex justify-around pt-1 pb-1">
        {navItems.map((item) => {
          const isActive =
            item.path === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(item.path);
          const Icon = item.icon;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex flex-col items-center pt-1.5 pb-1 px-3 text-[11px] transition-all duration-200 cursor-pointer min-w-[44px] min-h-[44px] relative ${
                isActive
                  ? "text-[#0096C7] dark:text-sky-400"
                  : "text-gray-400 dark:text-gray-500"
              }`}
            >
              <Icon size={20} className="mb-0.5" />
              <span className={isActive ? "font-medium" : ""}>{item.label}</span>
              {isActive && (
                <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-[#0096C7] dark:bg-sky-400" />
              )}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
