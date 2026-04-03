import { useQuery } from "@tanstack/react-query";
import { Share2, Inbox } from "lucide-react";
import { api } from "@/api/client";
import { BookmarkCard } from "@/components/bookmark/BookmarkCard";

type SharedItem = {
  id: string;
  title: string | null;
  description: string | null;
  url: string | null;
  source_platform: string;
  item_type: string;
  summary: string | null;
  media: Array<{ type: string; url: string; role: string }>;
  is_favorite: boolean;
  created_at: string;
};

export default function SharedWithMe() {
  const { data: items, isLoading } = useQuery<SharedItem[]>({
    queryKey: ["shared-with-me"],
    queryFn: () => api.get("/api/v1/shares/shared-with-me"),
  });

  return (
    <div className="animate-fade-in max-w-4xl mx-auto px-4 md:px-6">
      <div className="flex items-center gap-3 mb-6">
        <Share2 className="w-6 h-6 text-sky-600" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Shared with Me</h1>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
              <div className="aspect-video animate-pulse bg-gray-100 dark:bg-gray-800" />
              <div className="p-4 space-y-2">
                <div className="h-3 w-20 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
                <div className="h-4 w-full animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : !items || items.length === 0 ? (
        <div className="text-center py-16 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <Inbox className="w-12 h-12 text-[#0096C7]/20 dark:text-sky-900 mx-auto mb-4" />
          <p className="text-gray-700 dark:text-gray-300 text-lg font-medium mb-1">Nothing shared yet</p>
          <p className="text-sm text-gray-400 dark:text-gray-500">Items shared with you by other users will appear here</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <BookmarkCard key={item.id} item={item} variant="grid" />
          ))}
        </div>
      )}
    </div>
  );
}
