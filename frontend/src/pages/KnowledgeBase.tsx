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
} from "lucide-react";
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

  const filters =
    platform !== "All" ? { source_platform: platform.toLowerCase() } : {};
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useItems(filters);

  const items = data?.pages.flat() ?? [];

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
              <BookmarkCard key={item.id} item={item} variant={viewMode} />
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
    </div>
  );
}
