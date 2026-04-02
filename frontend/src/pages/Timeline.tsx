import { Clock, Loader2, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

interface TimelineDay {
  date: string;
  items: Array<{
    id: string;
    title: string;
    url: string | null;
    source_platform: string;
    item_type: string;
    summary: string | null;
    created_at: string;
  }>;
}

export default function Timeline() {
  const { data: timeline, isLoading } = useQuery<TimelineDay[]>({
    queryKey: ["timeline"],
    queryFn: () => api.get("/api/v1/items/timeline?days=30"),
  });

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === today.toDateString()) return "Today";
    if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
    return d.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });
  };

  return (
    <div className="animate-fade-in max-w-3xl mx-auto px-4">
      <div className="flex items-center gap-3 mb-6">
        <Clock className="w-6 h-6 text-sky-600" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Timeline</h1>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-sky-600" /></div>
      ) : !timeline?.length ? (
        <div className="text-center py-20">
          <Clock className="w-12 h-12 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400">No items in the last 30 days</p>
        </div>
      ) : (
        <div className="space-y-8">
          {timeline.map((day) => (
            <div key={day.date}>
              <div className="flex items-center gap-3 mb-3">
                <div className="w-3 h-3 rounded-full bg-sky-600 flex-shrink-0" />
                <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{formatDate(day.date)}</h2>
                <span className="text-xs text-gray-400">{day.items.length} items</span>
                <div className="flex-1 border-t border-gray-200 dark:border-gray-800" />
              </div>
              <div className="ml-6 space-y-2">
                {day.items.map((item) => (
                  <Link
                    key={item.id}
                    to={`/item/${item.id}`}
                    className="flex items-start gap-3 p-3 rounded-xl border border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-all cursor-pointer"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{item.title}</p>
                      {item.summary && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-1">{item.summary}</p>
                      )}
                      <div className="flex items-center gap-2 mt-1 text-[10px] text-gray-400">
                        <span className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">{item.source_platform}</span>
                        <span>{new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                      </div>
                    </div>
                    {item.url && <ExternalLink className="w-3.5 h-3.5 text-gray-400 flex-shrink-0 mt-1" />}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
