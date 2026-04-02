import { useQuery } from "@tanstack/react-query";
import { Share2, Inbox } from "lucide-react";
import { api } from "@/api/client";
import { BookmarkCard } from "@/components/bookmark/BookmarkCard";

export default function SharedWithMe() {
  const { data: items, isLoading } = useQuery<any[]>({
    queryKey: ["shared-with-me"],
    queryFn: () => api.get("/api/v1/shared-with-me"),
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
            <div key={i} className="h-48 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-xl" />
          ))}
        </div>
      ) : !items || items.length === 0 ? (
        <div className="text-center py-16 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm">
          <Inbox className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 text-lg mb-1">Nothing shared yet</p>
          <p className="text-sm text-gray-400 dark:text-gray-500">Items shared with you by other users will appear here</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item: any) => (
            <BookmarkCard key={item.id} item={item} variant="grid" />
          ))}
        </div>
      )}
    </div>
  );
}
