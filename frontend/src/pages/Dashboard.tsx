import { useState } from "react";
import { Link } from "react-router-dom";
import { BookOpen, Plus, ChevronDown, StickyNote, Inbox, Clock } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useItems } from "@/hooks/use-items";
import { BookmarkCard } from "@/components/bookmark/BookmarkCard";

interface Stats {
  total_items: number;
  items_this_week: number;
  total_tags: number;
  total_notes: number;
  total_collections: number;
  platforms: Record<string, number>;
  top_tags: Array<{ name: string; count: number }>;
}

export default function Dashboard() {
  const { data: stats, isLoading: statsLoading, isError: statsError } = useQuery<Stats>({
    queryKey: ["stats"],
    queryFn: () => api.get("/api/v1/stats"),
  });

  const { data, isLoading: itemsLoading, isError: itemsError } = useItems();

  const [visibleCount, setVisibleCount] = useState(8);
  const allItems = data?.pages.flat() ?? [];
  const recentItems = allItems.slice(0, visibleCount);
  const hasMore = allItems.length > visibleCount;

  if (statsError || itemsError) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400 text-sm">
          Failed to load dashboard data. Please try refreshing the page.
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in max-w-7xl mx-auto space-y-8">
      {/* Action tiles — verb-oriented, not vanity counts */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        {[
          { label: "Browse all", value: stats?.total_items, suffix: "items", icon: BookOpen, link: "/knowledge" },
          { label: "Added this week", value: stats?.items_this_week, suffix: "new", icon: Inbox, link: "/knowledge" },
          { label: "Open notes", value: stats?.total_notes, suffix: "notes", icon: StickyNote, link: "/notes" },
          { label: "Continue reading", value: null, suffix: "", icon: Clock, link: "/reading-list" },
        ].map((tile) => {
          const Icon = tile.icon;
          return (
            <Link
              key={tile.label}
              to={tile.link}
              className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 md:p-5 hover:border-sky-200 dark:hover:border-sky-800 transition-colors duration-200 cursor-pointer"
            >
              <div className="flex items-center gap-2.5 mb-3">
                <div className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                  <Icon className="h-4 w-4 md:h-5 md:w-5" />
                </div>
              </div>
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                {tile.label}
              </p>
              {tile.value != null && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  {statsLoading ? (
                    <span className="inline-block w-8 h-3 animate-pulse bg-gray-200 dark:bg-gray-800 rounded" />
                  ) : (
                    `${tile.value} ${tile.suffix}`
                  )}
                </p>
              )}
            </Link>
          );
        })}
      </div>

      {/* Recent Items */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg md:text-xl font-bold text-gray-900 dark:text-gray-100">
            Recent Items
          </h2>
          <Link
            to="/knowledge"
            className="text-sm text-[#0096C7] hover:text-[#0077A8] font-medium transition-colors cursor-pointer"
          >
            View all →
          </Link>
        </div>

        {itemsLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
                <div className="aspect-video animate-pulse bg-gray-100 dark:bg-gray-800" />
                <div className="p-4 space-y-2">
                  <div className="h-3 w-16 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
                  <div className="h-4 w-full animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
                  <div className="h-3 w-3/4 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : recentItems.length === 0 ? (
          <div className="text-center py-16 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
            <BookOpen className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
            <p className="text-gray-700 dark:text-gray-300 text-lg font-medium mb-1">
              No saved items
            </p>
            <p className="text-gray-400 dark:text-gray-500 text-sm mb-6">
              Save a URL or create a note to get started.
            </p>
            <Link
              to="/add"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0096C7] text-white rounded-xl font-medium hover:bg-[#0077A8] hover:shadow-lg transition-all duration-200 cursor-pointer"
            >
              <Plus className="h-4 w-4" />
              Add your first item
            </Link>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {recentItems.map((item) => (
                <BookmarkCard key={item.id} item={item} variant="grid" />
              ))}
            </div>
            {hasMore && (
              <div className="mt-6 text-center">
                <button
                  onClick={() => setVisibleCount((c) => c + 8)}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-xl text-sm font-medium hover:shadow-md transition-all duration-200 cursor-pointer"
                >
                  <ChevronDown className="h-4 w-4" />
                  View more
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
