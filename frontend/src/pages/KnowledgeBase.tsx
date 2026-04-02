import { useState } from "react";
import {
  BookOpen,
  Grid3x3,
  List,
  Play,
  GitBranch,
  MessageSquare,
  Globe,
  Newspaper,
  Hash,
  Camera,
  Loader2,
  CheckSquare,
} from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useItems } from "@/hooks/use-items";
import { useUIStore } from "@/stores/ui-store";
import { BookmarkCard } from "@/components/bookmark/BookmarkCard";

const PLATFORMS: { key: string; label: string; icon: React.ReactNode }[] = [
  { key: "All", label: "All", icon: <Globe className="h-4 w-4" /> },
  { key: "YouTube", label: "YouTube", icon: <Play className="h-4 w-4" /> },
  { key: "Reddit", label: "Reddit", icon: <MessageSquare className="h-4 w-4" /> },
  { key: "GitHub", label: "GitHub", icon: <GitBranch className="h-4 w-4" /> },
  { key: "Twitter", label: "Twitter", icon: <Hash className="h-4 w-4" /> },
  { key: "HackerNews", label: "HackerNews", icon: <Newspaper className="h-4 w-4" /> },
  { key: "Medium", label: "Medium", icon: <BookOpen className="h-4 w-4" /> },
  { key: "Substack", label: "Substack", icon: <Camera className="h-4 w-4" /> },
];

export default function KnowledgeBase() {
  const [platform, setPlatform] = useState("All");
  const { viewMode, setViewMode } = useUIStore();
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const qc = useQueryClient();

  const filters =
    platform !== "All" ? { source_platform: platform.toLowerCase() } : {};
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useItems(filters);

  const items = data?.pages.flat() ?? [];

  const bulkAction = useMutation({
    mutationFn: (data: { action: string; item_ids: string[]; tag_name?: string }) =>
      api.post("/api/v1/items/bulk", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["items"] });
      setSelected(new Set());
      setSelecting(false);
    },
  });

  const toggleSelectItem = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleBulkTag = () => {
    const tag = prompt("Enter tag name:");
    if (!tag?.trim()) return;
    bulkAction.mutate({ action: "tag", item_ids: Array.from(selected), tag_name: tag.trim() });
  };

  const handleBulkArchive = () => {
    bulkAction.mutate({ action: "archive", item_ids: Array.from(selected) });
  };

  const handleBulkDelete = () => {
    if (!confirm(`Delete ${selected.size} item(s)?`)) return;
    bulkAction.mutate({ action: "delete", item_ids: Array.from(selected) });
  };

  return (
    <div className="animate-fade-in p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <BookOpen className="h-6 w-6 text-sky-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Knowledge Base
          </h1>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => {
              setSelecting((v) => !v);
              setSelected(new Set());
            }}
            className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer ${
              selecting
                ? "bg-sky-600 text-white"
                : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-md"
            }`}
            aria-label="Toggle selection mode"
          >
            <CheckSquare className="h-4 w-4" />
            <span className="hidden sm:inline">Select</span>
          </button>
          <button
            onClick={() => setViewMode("grid")}
            className={`p-2.5 rounded-lg text-sm transition-all duration-200 cursor-pointer ${
              viewMode === "grid"
                ? "bg-sky-600 text-white"
                : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-md"
            }`}
            aria-label="Grid view"
          >
            <Grid3x3 className="h-4 w-4" />
          </button>
          <button
            onClick={() => setViewMode("list")}
            className={`p-2.5 rounded-lg text-sm transition-all duration-200 cursor-pointer ${
              viewMode === "list"
                ? "bg-sky-600 text-white"
                : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-md"
            }`}
            aria-label="List view"
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="flex gap-2 flex-wrap mb-6">
        {PLATFORMS.map((p) => (
          <button
            key={p.key}
            onClick={() => setPlatform(p.key)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200 cursor-pointer ${
              platform === p.key
                ? "bg-sky-600 text-white"
                : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-md"
            }`}
          >
            {p.icon}
            {p.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="h-48 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg"
            />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm">
          <BookOpen className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 text-lg mb-1">
            No items found
          </p>
          <p className="text-gray-400 dark:text-gray-500 text-sm">
            Try a different filter or add some content
          </p>
        </div>
      ) : (
        <>
          <div
            className={
              viewMode === "grid"
                ? "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
                : "flex flex-col gap-3"
            }
          >
            {items.map((item) => (
              selecting ? (
                <div
                  key={item.id}
                  className="relative cursor-pointer"
                  onClick={() => toggleSelectItem(item.id)}
                >
                  <div className={`absolute top-2 left-2 z-10 w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all duration-150 ${
                    selected.has(item.id)
                      ? "bg-sky-600 border-sky-600"
                      : "bg-white dark:bg-gray-900 border-gray-300 dark:border-gray-600"
                  }`}>
                    {selected.has(item.id) && (
                      <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 12 12">
                        <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </div>
                  <div className={`pointer-events-none transition-all duration-150 ${selected.has(item.id) ? "ring-2 ring-sky-500 rounded-xl" : ""}`}>
                    <BookmarkCard item={item} variant={viewMode} />
                  </div>
                </div>
              ) : (
                <BookmarkCard key={item.id} item={item} variant={viewMode} />
              )
            ))}
          </div>

          {hasNextPage && (
            <div className="mt-8 text-center">
              <button
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-md transition-all duration-200 cursor-pointer disabled:opacity-50"
              >
                {isFetchingNextPage ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading...
                  </>
                ) : (
                  "Load more"
                )}
              </button>
            </div>
          )}
        </>
      )}

      {selecting && selected.size > 0 && (
        <div className="fixed bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-50 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl shadow-xl px-4 py-3 flex items-center gap-3">
          <span className="text-sm font-medium text-gray-600 dark:text-gray-300">{selected.size} selected</span>
          <button onClick={handleBulkTag} className="px-3 py-1.5 rounded-lg bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-400 text-sm font-medium hover:bg-sky-200 dark:hover:bg-sky-900/50 transition-all cursor-pointer">Tag</button>
          <button onClick={handleBulkArchive} className="px-3 py-1.5 rounded-lg bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 text-sm font-medium hover:bg-amber-200 dark:hover:bg-amber-900/50 transition-all cursor-pointer">Archive</button>
          <button onClick={handleBulkDelete} className="px-3 py-1.5 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-sm font-medium hover:bg-red-200 dark:hover:bg-red-900/50 transition-all cursor-pointer">Delete</button>
          <button onClick={() => { setSelecting(false); setSelected(new Set()); }} className="px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-sm cursor-pointer">Cancel</button>
        </div>
      )}
    </div>
  );
}
