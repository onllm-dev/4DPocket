import { Link } from "react-router-dom";
import { LayoutDashboard, BookOpen, TrendingUp, Tags, Plus, FolderOpen } from "lucide-react";
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
  const { data: stats, isLoading: statsLoading } = useQuery<Stats>({
    queryKey: ["stats"],
    queryFn: () => api.get("/api/v1/stats"),
  });

  const { data, isLoading: itemsLoading } = useItems();

  const allItems = data?.pages.flat() ?? [];
  const recentItems = allItems.slice(0, 8);
  const totalItems = stats?.total_items ?? 0;

  return (
    <div className="animate-fade-in p-6 max-w-6xl mx-auto">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-1">
          <LayoutDashboard className="h-7 w-7 text-[#0096C7]" />
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            Your 4DPocket
          </h1>
        </div>
        <p className="text-gray-500 dark:text-gray-400 mt-1 italic">
          {statsLoading
            ? "Loading your pocket..."
            : totalItems === 0
            ? "Your pocket is empty — time to fill it up!"
            : `Your pocket has ${totalItems} item${totalItems === 1 ? "" : "s"} — reach in and explore.`}
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="rounded-2xl border border-sky-100 dark:border-gray-800 bg-gradient-to-br from-sky-50 to-white dark:from-sky-950/30 dark:to-gray-900 shadow-sm p-5 hover:shadow-md transition-all duration-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-xl bg-[#0096C7]/10 dark:bg-sky-900/20">
              <BookOpen className="h-5 w-5 text-[#0096C7]" />
            </div>
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Total Items
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            {statsLoading ? (
              <span className="inline-block w-12 h-8 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-xl" />
            ) : (
              stats?.total_items ?? 0
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-sky-100 dark:border-gray-800 bg-gradient-to-br from-emerald-50 to-white dark:from-emerald-950/20 dark:to-gray-900 shadow-sm p-5 hover:shadow-md transition-all duration-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-900/20">
              <TrendingUp className="h-5 w-5 text-emerald-600" />
            </div>
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              This Week
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            {statsLoading ? (
              <span className="inline-block w-12 h-8 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-xl" />
            ) : (
              stats?.items_this_week ?? 0
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-sky-100 dark:border-gray-800 bg-gradient-to-br from-violet-50 to-white dark:from-violet-950/20 dark:to-gray-900 shadow-sm p-5 hover:shadow-md transition-all duration-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-xl bg-violet-50 dark:bg-violet-900/20">
              <Tags className="h-5 w-5 text-violet-600" />
            </div>
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Tags
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            {statsLoading ? (
              <span className="inline-block w-12 h-8 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-xl" />
            ) : (
              stats?.total_tags ?? 0
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-sky-100 dark:border-gray-800 bg-gradient-to-br from-amber-50 to-white dark:from-amber-950/20 dark:to-gray-900 shadow-sm p-5 hover:shadow-md transition-all duration-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-xl bg-amber-50 dark:bg-amber-900/20">
              <FolderOpen className="h-5 w-5 text-amber-600" />
            </div>
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Collections
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            {statsLoading ? (
              <span className="inline-block w-12 h-8 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-xl" />
            ) : (
              stats?.total_collections ?? 0
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
          Recent Items
        </h2>
        <Link
          to="/knowledge"
          className="text-sm text-[#0096C7] hover:underline cursor-pointer"
        >
          View all
        </Link>
      </div>

      {itemsLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-48 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-2xl"
            />
          ))}
        </div>
      ) : recentItems.length === 0 ? (
        <div className="text-center py-16 rounded-2xl border border-sky-100 dark:border-gray-800 bg-gradient-to-br from-sky-50 to-white dark:from-sky-950/20 dark:to-gray-900 shadow-sm">
          <BookOpen className="h-12 w-12 text-[#0096C7]/30 dark:text-sky-700 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 text-lg mb-1">
            Nothing saved yet
          </p>
          <p className="text-gray-400 dark:text-gray-500 text-sm mb-6">
            Toss something into your pocket to get started
          </p>
          <Link
            to="/add"
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0096C7] text-white rounded-xl font-medium hover:bg-[#0077A8] hover:shadow-md transition-all duration-200 cursor-pointer"
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
          <div className="mt-8 text-center">
            <Link
              to="/add"
              className="inline-flex items-center gap-2 px-6 py-3 bg-[#0096C7] text-white rounded-xl font-medium hover:bg-[#0077A8] hover:shadow-md transition-all duration-200 cursor-pointer"
            >
              <Plus className="h-4 w-4" />
              Add something
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
