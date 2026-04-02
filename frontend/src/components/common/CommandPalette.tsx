import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Home, BookOpen, FolderOpen, Tags, FileText, Settings, Plus } from "lucide-react";
import { api } from "@/api/client";

const NAV_ITEMS = [
  { label: "Dashboard", path: "/", icon: Home },
  { label: "Knowledge Base", path: "/knowledge", icon: BookOpen },
  { label: "Collections", path: "/collections", icon: FolderOpen },
  { label: "Tags", path: "/tags", icon: Tags },
  { label: "Notes", path: "/notes", icon: FileText },
  { label: "Settings", path: "/settings", icon: Settings },
  { label: "Add Item", path: "/add", icon: Plus },
];

interface SearchResult {
  id: string;
  title: string;
  source_platform: string;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // Open/close with Cmd+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setQuery("");
      setResults([]);
      setActiveIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Search as user types (debounced)
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const data = await api.get<{ items: SearchResult[] }>(`/api/v1/search?q=${encodeURIComponent(query)}&limit=5`);
        setResults(Array.isArray(data) ? data : data.items || []);
      } catch {
        setResults([]);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [query]);

  const filteredNav = query
    ? NAV_ITEMS.filter((item) => item.label.toLowerCase().includes(query.toLowerCase()))
    : NAV_ITEMS;

  const allItems = [
    ...filteredNav.map((n) => ({ type: "nav" as const, ...n })),
    ...results.map((r) => ({ type: "result" as const, label: r.title, path: `/item/${r.id}`, id: r.id })),
  ];

  const handleSelect = useCallback(
    (path: string) => {
      navigate(path);
      setOpen(false);
    },
    [navigate]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, allItems.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && allItems[activeIndex]) {
      handleSelect(allItems[activeIndex].path);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh] px-4"
      onClick={() => setOpen(false)}
    >
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-lg bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-800 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200 dark:border-gray-800">
          <Search className="w-5 h-5 text-gray-400 flex-shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Search or jump to..."
            className="flex-1 bg-transparent text-gray-900 dark:text-gray-100 placeholder-gray-400 outline-none text-sm"
          />
          <kbd className="hidden sm:inline-flex text-[10px] text-gray-400 bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">
            ESC
          </kbd>
        </div>

        {/* Results list */}
        <div className="max-h-80 overflow-y-auto py-2">
          {allItems.length === 0 && query && (
            <p className="text-sm text-gray-400 text-center py-6">No results</p>
          )}
          {!query && (
            <p className="text-[10px] uppercase tracking-wider text-gray-400 px-4 py-1">Navigate</p>
          )}
          {query && results.length > 0 && filteredNav.length > 0 && (
            <p className="text-[10px] uppercase tracking-wider text-gray-400 px-4 py-1">Pages</p>
          )}
          {filteredNav.map((item, i) => {
            const Icon = item.icon;
            return (
              <button
                key={item.path}
                onClick={() => handleSelect(item.path)}
                className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors cursor-pointer ${
                  activeIndex === i
                    ? "bg-sky-50 dark:bg-sky-950 text-sky-600"
                    : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                }`}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span>{item.label}</span>
              </button>
            );
          })}
          {results.length > 0 && (
            <>
              <p className="text-[10px] uppercase tracking-wider text-gray-400 px-4 py-1 mt-1">Items</p>
              {results.map((r, i) => (
                <button
                  key={r.id}
                  onClick={() => handleSelect(`/item/${r.id}`)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors cursor-pointer ${
                    activeIndex === filteredNav.length + i
                      ? "bg-sky-50 dark:bg-sky-950 text-sky-600"
                      : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                  }`}
                >
                  <Search className="w-4 h-4 flex-shrink-0 text-gray-400" />
                  <span className="truncate">{r.title}</span>
                  <span className="text-[10px] text-gray-400 ml-auto flex-shrink-0">{r.source_platform}</span>
                </button>
              ))}
            </>
          )}
        </div>

        {/* Footer hints */}
        <div className="px-4 py-2 border-t border-gray-200 dark:border-gray-800 flex items-center gap-4 text-[10px] text-gray-400">
          <span>
            <kbd className="bg-gray-100 dark:bg-gray-800 px-1 rounded">↑↓</kbd> navigate
          </span>
          <span>
            <kbd className="bg-gray-100 dark:bg-gray-800 px-1 rounded">↵</kbd> select
          </span>
          <span>
            <kbd className="bg-gray-100 dark:bg-gray-800 px-1 rounded">esc</kbd> close
          </span>
        </div>
      </div>
    </div>
  );
}
