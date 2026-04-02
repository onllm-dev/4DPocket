import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Plus, Sun, Moon, Monitor } from "lucide-react";
import { useUIStore } from "@/stores/ui-store";

export function Header() {
  const [searchQuery, setSearchQuery] = useState("");
  const navigate = useNavigate();
  const theme = useUIStore((s) => s.theme);
  const setTheme = useUIStore((s) => s.setTheme);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery)}`);
    }
  };

  const cycleTheme = () => {
    const next = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
    setTheme(next);
  };

  const ThemeIcon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;

  return (
    <header className="flex items-center gap-3 px-4 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 min-h-[60px]">
      <form onSubmit={handleSearch} className="flex-1 max-w-xl relative">
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500 pointer-events-none"
        />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search your knowledge base... (Cmd+K)"
          className="w-full pl-9 pr-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all duration-200 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500"
        />
      </form>

      <button
        onClick={() => navigate("/add")}
        className="flex items-center gap-2 px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer shadow-sm hover:shadow-md min-h-[44px]"
      >
        <Plus size={16} />
        <span>Add</span>
      </button>

      <button
        onClick={cycleTheme}
        className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-all duration-200 cursor-pointer text-gray-600 dark:text-gray-400 min-w-[44px] min-h-[44px] flex items-center justify-center"
        title={`Theme: ${theme}`}
        aria-label={`Switch theme (current: ${theme})`}
      >
        <ThemeIcon size={18} />
      </button>
    </header>
  );
}
