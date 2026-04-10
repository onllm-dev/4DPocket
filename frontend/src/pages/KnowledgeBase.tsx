import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  BookOpen,
  Grid3x3,
  List,
  Globe,
  Loader2,
  CheckSquare,
  RefreshCw,
  ArrowUpDown,
} from "lucide-react";
import { PlatformIcon } from "@/components/common/PlatformIcon";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useItems } from "@/hooks/use-items";
import { useNotes } from "@/hooks/use-notes";
import { useUIStore } from "@/stores/ui-store";
import { BookmarkCard } from "@/components/bookmark/BookmarkCard";
import NoteCard from "@/components/bookmark/NoteCard";

const PLATFORMS: { key: string; label: string; icon: React.ReactNode }[] = [
  { key: "All", label: "All", icon: <Globe className="h-4 w-4" /> },
  { key: "YouTube", label: "YouTube", icon: <PlatformIcon platform="youtube" className="h-4 w-4" /> },
  { key: "Reddit", label: "Reddit", icon: <PlatformIcon platform="reddit" className="h-4 w-4" /> },
  { key: "GitHub", label: "GitHub", icon: <PlatformIcon platform="github" className="h-4 w-4" /> },
  { key: "Twitter", label: "Twitter", icon: <PlatformIcon platform="twitter" className="h-4 w-4" /> },
  { key: "HackerNews", label: "HackerNews", icon: <PlatformIcon platform="hackernews" className="h-4 w-4" /> },
  { key: "Medium", label: "Medium", icon: <PlatformIcon platform="medium" className="h-4 w-4" /> },
  { key: "Substack", label: "Substack", icon: <PlatformIcon platform="substack" className="h-4 w-4" /> },
];

export default function KnowledgeBase() {
  const [searchParams] = useSearchParams();
  const isFavorite = searchParams.get("is_favorite") === "true" ? true : undefined;
  const isArchived = searchParams.get("is_archived") === "true" ? true : undefined;
  const tagId = searchParams.get("tag_id") || undefined;
  const [platform, setPlatform] = useState("All");
  const [sortKey, setSortKey] = useState("created_at:desc");
  const { viewMode, setViewMode } = useUIStore();
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkTagInput, setBulkTagInput] = useState("");
  const [showBulkTagInput, setShowBulkTagInput] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const qc = useQueryClient();

  const handleRefresh = async () => {
    setRefreshing(true);
    await qc.invalidateQueries({ queryKey: ["items"] });
    setTimeout(() => setRefreshing(false), 500);
  };

  const [sortBy, sortOrder] = sortKey.split(":");
  const filters: Record<string, unknown> = { sort_by: sortBy, sort_order: sortOrder };
  if (platform !== "All") filters.source_platform = platform.toLowerCase();
  if (isFavorite) filters.is_favorite = true;
  if (isArchived) filters.is_archived = true;
  if (tagId) filters.tag_id = tagId;
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useItems(filters);

  const items = data?.pages.flat() ?? [];
  const { data: notes } = useNotes({ is_archived: isArchived, is_favorite: isFavorite });

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
    if (!bulkTagInput.trim()) return;
    bulkAction.mutate({ action: "tag", item_ids: Array.from(selected), tag_name: bulkTagInput.trim() });
    setBulkTagInput("");
    setShowBulkTagInput(false);
  };

  const handleBulkArchive = () => {
    bulkAction.mutate({ action: "archive", item_ids: Array.from(selected) });
  };

  const handleBulkDelete = () => {
    bulkAction.mutate({ action: "delete", item_ids: Array.from(selected) });
    setConfirmDelete(false);
  };

  return (
    <div className="animate-fade-in max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {isFavorite ? "Favorites" : isArchived ? "Archive" : tagId ? "Tagged Items" : "Knowledge Base"}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            {isFavorite ? "Your starred items" : isArchived ? "Archived items" : tagId ? "Filtered by tag" : "All your saved knowledge in one place"}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <div className="relative inline-flex items-center">
            <ArrowUpDown className="absolute left-2 h-3.5 w-3.5 text-gray-500 pointer-events-none" />
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value)}
              className="pl-7 pr-3 py-2 rounded-lg text-sm bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-none outline-none cursor-pointer hover:shadow-md transition-all duration-200 appearance-none"
              aria-label="Sort order"
            >
              <option value="created_at:desc">Newest first</option>
              <option value="created_at:asc">Oldest first</option>
              <option value="title:asc">Title A-Z</option>
              <option value="title:desc">Title Z-A</option>
              <option value="updated_at:desc">Recently updated</option>
            </select>
          </div>
          <button
            onClick={handleRefresh}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-all cursor-pointer"
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 text-gray-500 ${refreshing ? "animate-spin" : ""}`} />
          </button>
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

      {refreshing && (
        <div className="flex items-center justify-center py-3">
          <Loader2 className="w-5 h-5 animate-spin text-sky-600" />
          <span className="text-sm text-gray-400 ml-2">Refreshing...</span>
        </div>
      )}

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
            <div key={i} className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
              <div className="aspect-video animate-pulse bg-gray-100 dark:bg-gray-800" />
              <div className="p-4 space-y-2">
                <div className="h-3 w-20 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
                <div className="h-4 w-full animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-3 w-3/4 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <BookOpen className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-700 dark:text-gray-300 text-lg font-medium mb-1">
            No items found
          </p>
          <p className="text-gray-400 dark:text-gray-500 text-sm">
            {platform !== "All" ? `No ${platform} items found. Try a different platform filter.` : "Try a different filter or add some content."}
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
            {/* Notes in knowledge base */}
            {platform === "All" && notes && notes.length > 0 && !selecting && notes.map((note) => (
              <NoteCard key={`note-${note.id}`} note={note} variant={viewMode === "list" ? "compact" : "grid"} />
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
        <div className="fixed bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-50 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl shadow-xl px-4 py-3 flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-gray-600 dark:text-gray-300">{selected.size} selected</span>
          {showBulkTagInput ? (
            <>
              <input
                type="text"
                value={bulkTagInput}
                onChange={(e) => setBulkTagInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleBulkTag()}
                placeholder="Tag name..."
                autoFocus
                className="px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              <button onClick={handleBulkTag} disabled={!bulkTagInput.trim()} className="px-3 py-1.5 rounded-lg bg-sky-600 text-white text-sm font-medium hover:bg-sky-700 transition-all cursor-pointer disabled:opacity-50">Apply</button>
              <button onClick={() => { setShowBulkTagInput(false); setBulkTagInput(""); }} className="px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-sm cursor-pointer">Cancel</button>
            </>
          ) : confirmDelete ? (
            <>
              <span className="text-sm text-red-600 dark:text-red-400">Delete {selected.size} item(s)?</span>
              <button onClick={handleBulkDelete} className="px-3 py-1.5 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition-all cursor-pointer">Confirm</button>
              <button onClick={() => setConfirmDelete(false)} className="px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-sm cursor-pointer">Cancel</button>
            </>
          ) : (
            <>
              <button onClick={() => setShowBulkTagInput(true)} className="px-3 py-1.5 rounded-lg bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-400 text-sm font-medium hover:bg-sky-200 dark:hover:bg-sky-900/50 transition-all cursor-pointer">Tag</button>
              <button onClick={handleBulkArchive} className="px-3 py-1.5 rounded-lg bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 text-sm font-medium hover:bg-amber-200 dark:hover:bg-amber-900/50 transition-all cursor-pointer">Archive</button>
              <button onClick={() => setConfirmDelete(true)} className="px-3 py-1.5 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-sm font-medium hover:bg-red-200 dark:hover:bg-red-900/50 transition-all cursor-pointer">Delete</button>
              <button onClick={() => { setSelecting(false); setSelected(new Set()); }} className="px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-sm cursor-pointer">Cancel</button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
