import { Link } from "react-router-dom";
import { LayoutDashboard, BookOpen, TrendingUp, Tags, Plus } from "lucide-react";
import { useItems } from "@/hooks/use-items";
import { BookmarkCard } from "@/components/bookmark/BookmarkCard";

export default function Dashboard() {
  const { data, isLoading } = useItems();

  const allItems = data?.pages.flat() ?? [];
  const recentItems = allItems.slice(0, 8);

  const oneWeekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const thisWeekCount = allItems.filter(
    (item) => new Date(item.created_at).getTime() > oneWeekAgo
  ).length;

  const uniqueTags = new Set(
    allItems.flatMap((item) => {
      const meta = item.item_metadata as Record<string, unknown>;
      return Array.isArray(meta?.tags) ? (meta.tags as string[]) : [];
    })
  );

  return (
    <div className="animate-fade-in p-6 max-w-6xl mx-auto">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-1">
          <LayoutDashboard className="h-7 w-7 text-sky-600" />
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            Your 4DPocket
          </h1>
        </div>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Your personal knowledge base
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5 hover:shadow-md transition-all duration-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-lg bg-sky-50 dark:bg-sky-900/20">
              <BookOpen className="h-5 w-5 text-sky-600" />
            </div>
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Total Items
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            {isLoading ? (
              <span className="inline-block w-12 h-8 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg" />
            ) : (
              allItems.length
            )}
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5 hover:shadow-md transition-all duration-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-900/20">
              <TrendingUp className="h-5 w-5 text-emerald-600" />
            </div>
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              This Week
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            {isLoading ? (
              <span className="inline-block w-12 h-8 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg" />
            ) : (
              thisWeekCount
            )}
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5 hover:shadow-md transition-all duration-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-lg bg-violet-50 dark:bg-violet-900/20">
              <Tags className="h-5 w-5 text-violet-600" />
            </div>
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Tags
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            {isLoading ? (
              <span className="inline-block w-12 h-8 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg" />
            ) : (
              uniqueTags.size
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
          className="text-sm text-sky-600 hover:underline cursor-pointer"
        >
          View all
        </Link>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-48 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg"
            />
          ))}
        </div>
      ) : recentItems.length === 0 ? (
        <div className="text-center py-16 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm">
          <BookOpen className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 text-lg mb-1">
            Nothing saved yet
          </p>
          <p className="text-gray-400 dark:text-gray-500 text-sm mb-6">
            Start building your knowledge base
          </p>
          <Link
            to="/add"
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-sky-600 text-white rounded-lg font-medium hover:shadow-md transition-all duration-200 cursor-pointer"
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
              className="inline-flex items-center gap-2 px-6 py-3 bg-sky-600 text-white rounded-xl font-medium hover:shadow-md transition-all duration-200 cursor-pointer"
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
