import { Rss, Loader2, ExternalLink } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import { timeAgo } from "@/lib/utils";

interface FeedItem {
  id: string;
  title: string;
  url: string | null;
  source_platform: string;
  summary: string | null;
  created_at: string;
  owner_display_name: string;
}

export default function Feed() {
  const { data: items, isLoading } = useQuery<FeedItem[]>({
    queryKey: ["feeds"],
    queryFn: () => api.get("/api/v1/feeds"),
  });

  return (
    <div className="animate-fade-in max-w-3xl mx-auto px-4">
      <div className="flex items-center gap-3 mb-6">
        <Rss className="w-6 h-6 text-sky-600" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Knowledge Feed</h1>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 animate-spin text-sky-600" />
        </div>
      ) : !items?.length ? (
        <div className="text-center py-20">
          <Rss className="w-12 h-12 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400">No feed items yet</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">Follow other users to see their public knowledge here</p>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <Link
              key={item.id}
              to={`/item/${item.id}`}
              className="block rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 hover:shadow-md transition-all duration-200"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <h3 className="font-medium text-gray-900 dark:text-gray-100 truncate">{item.title}</h3>
                  {item.summary && (
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">{item.summary}</p>
                  )}
                  <div className="flex items-center gap-2 mt-2 text-xs text-gray-400">
                    <span>{item.owner_display_name}</span>
                    <span>·</span>
                    <span>{item.source_platform}</span>
                    <span>·</span>
                    <span>{timeAgo(item.created_at)}</span>
                  </div>
                </div>
                {item.url && (
                  <a href={item.url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-sky-600 hover:text-sky-700 flex-shrink-0">
                    <ExternalLink className="w-4 h-4" />
                  </a>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
