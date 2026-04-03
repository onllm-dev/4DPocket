import { useState } from "react";
import { Link } from "react-router-dom";
import { LayoutDashboard, BookOpen, TrendingUp, Tags, Plus, FolderOpen, ChevronDown } from "lucide-react";
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
  const totalItems = stats?.total_items ?? 0;

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
      {/* Hero header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#0096C7] to-[#0077A8] dark:from-[#0096C7]/90 dark:to-[#0C1222] p-6 md:p-8 text-white">
        <div className="absolute top-0 right-0 w-64 h-64 rounded-full bg-white/5 -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-0 w-32 h-32 rounded-full bg-[#FCD34D]/10 translate-y-1/2 -translate-x-1/2" />
        <div className="relative">
          <div className="flex items-center gap-3 mb-2">
            <LayoutDashboard className="h-6 w-6 text-white/80" />
            <h1 className="text-2xl md:text-3xl font-bold">
              Your 4DPocket
            </h1>
          </div>
          <p className="text-white/70 text-sm md:text-base max-w-lg">
            {statsLoading
              ? "Loading your pocket..."
              : totalItems === 0
              ? "Your pocket is empty — time to fill it up!"
              : `${totalItems} item${totalItems === 1 ? "" : "s"} saved. Reach in and explore.`}
          </p>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        {[
          { label: "Total Items", value: stats?.total_items, icon: BookOpen, color: "sky", gradient: "from-sky-50 to-white dark:from-sky-950/30 dark:to-gray-900" },
          { label: "This Week", value: stats?.items_this_week, icon: TrendingUp, color: "emerald", gradient: "from-emerald-50 to-white dark:from-emerald-950/20 dark:to-gray-900" },
          { label: "Tags", value: stats?.total_tags, icon: Tags, color: "violet", gradient: "from-violet-50 to-white dark:from-violet-950/20 dark:to-gray-900" },
          { label: "Collections", value: stats?.total_collections, icon: FolderOpen, color: "amber", gradient: "from-amber-50 to-white dark:from-amber-950/20 dark:to-gray-900" },
        ].map((stat) => {
          const Icon = stat.icon;
          const colorMap: Record<string, string> = {
            sky: "bg-[#0096C7]/10 dark:bg-sky-900/30 text-[#0096C7]",
            emerald: "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600",
            violet: "bg-violet-100 dark:bg-violet-900/30 text-violet-600",
            amber: "bg-amber-100 dark:bg-amber-900/30 text-amber-600",
          };
          return (
            <div
              key={stat.label}
              className={`rounded-2xl border border-gray-200/60 dark:border-gray-800 bg-gradient-to-br ${stat.gradient} p-4 md:p-5 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300`}
            >
              <div className="flex items-center gap-2.5 mb-3">
                <div className={`p-2 rounded-xl ${colorMap[stat.color]}`}>
                  <Icon className="h-4 w-4 md:h-5 md:w-5" />
                </div>
                <span className="text-xs md:text-sm font-medium text-gray-500 dark:text-gray-400">
                  {stat.label}
                </span>
              </div>
              <div className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-gray-100">
                {statsLoading ? (
                  <span className="inline-block w-10 h-7 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg" />
                ) : (
                  stat.value ?? 0
                )}
              </div>
            </div>
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
            <BookOpen className="h-12 w-12 text-[#0096C7]/20 dark:text-sky-900 mx-auto mb-4" />
            <p className="text-gray-700 dark:text-gray-300 text-lg font-medium mb-1">
              Nothing saved yet
            </p>
            <p className="text-gray-400 dark:text-gray-500 text-sm mb-6">
              Toss something into your pocket to get started
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
