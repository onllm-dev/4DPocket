import { Link, useLocation } from "react-router-dom";
import { Home, BookOpen, Search, FolderOpen, Settings } from "lucide-react";

const navItems = [
  { path: "/", label: "Home", icon: Home },
  { path: "/knowledge", label: "Library", icon: BookOpen },
  { path: "/search", label: "Search", icon: Search },
  { path: "/collections", label: "Collections", icon: FolderOpen },
  { path: "/settings", label: "Settings", icon: Settings },
];

export function BottomNav() {
  const location = useLocation();

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-950 border-t border-gray-200 dark:border-gray-800 z-50 pb-safe">
      <div className="flex justify-around pb-2">
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
              className={`flex flex-col items-center pt-2 px-3 text-xs transition-all duration-200 cursor-pointer min-w-[44px] min-h-[44px] ${
                isActive
                  ? "text-sky-600 dark:text-sky-400"
                  : "text-gray-500 dark:text-gray-400"
              }`}
            >
              <Icon size={20} className="mb-0.5" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
