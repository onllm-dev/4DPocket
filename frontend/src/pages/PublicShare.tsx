import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Globe, ExternalLink, Loader2, Calendar, Tag } from "lucide-react";
import { timeAgo } from "@/lib/utils";

interface PublicItem {
  id: string;
  title: string;
  url: string | null;
  description: string | null;
  content: string | null;
  summary: string | null;
  source_platform: string;
  created_at: string;
  tags: string[];
  owner_display_name: string;
}

export default function PublicShare() {
  const { token } = useParams<{ token: string }>();

  const { data: item, isLoading, error } = useQuery<PublicItem>({
    queryKey: ["public", token],
    queryFn: async () => {
      const res = await fetch(`/api/v1/public/${token}`);
      if (!res.ok) throw new Error(res.status === 404 ? "This share link is invalid or has expired" : "Failed to load");
      return res.json();
    },
    enabled: !!token,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <Loader2 className="w-8 h-8 animate-spin text-sky-600" />
      </div>
    );
  }

  if (error || !item) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950 px-4">
        <div className="text-center">
          <Globe className="w-12 h-12 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
          <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">Link Not Found</h1>
          <p className="text-gray-500 dark:text-gray-400">{(error as Error)?.message || "This share link is invalid or has expired"}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center gap-2">
          <Globe className="w-5 h-5 text-sky-600" />
          <span className="font-bold text-sky-600">4D</span>
          <span className="font-semibold text-gray-800 dark:text-gray-100">Pocket</span>
          <span className="text-xs text-gray-400 ml-2">Shared by {item.owner_display_name}</span>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-gray-100 mb-4">{item.title}</h1>

        <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500 dark:text-gray-400 mb-6">
          <span className="inline-flex items-center gap-1 bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded-lg text-xs">
            {item.source_platform}
          </span>
          {item.url && (
            <a href={item.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sky-600 hover:underline">
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Original</span>
            </a>
          )}
          <span className="inline-flex items-center gap-1">
            <Calendar className="w-3.5 h-3.5" />
            {timeAgo(item.created_at)}
          </span>
        </div>

        {item.tags?.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-6">
            {item.tags.map((tag) => (
              <span key={tag} className="inline-flex items-center gap-1 bg-sky-50 dark:bg-sky-900/20 text-sky-700 dark:text-sky-400 px-2 py-1 rounded-lg text-xs">
                <Tag className="w-3 h-3" />
                {tag}
              </span>
            ))}
          </div>
        )}

        {item.summary && (
          <div className="bg-sky-50 dark:bg-sky-900/20 rounded-xl p-4 mb-6">
            <p className="text-sm text-sky-800 dark:text-sky-300">{item.summary}</p>
          </div>
        )}

        {item.description && (
          <p className="text-gray-600 dark:text-gray-300 mb-6">{item.description}</p>
        )}

        {item.content && (
          <div className="prose dark:prose-invert max-w-none text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
            {item.content}
          </div>
        )}
      </main>

      <footer className="border-t border-gray-200 dark:border-gray-800 py-6 mt-12">
        <div className="max-w-3xl mx-auto px-4 text-center text-xs text-gray-400">
          Shared via <span className="font-semibold text-sky-600">4DPocket</span> — AI-powered personal knowledge base
        </div>
      </footer>
    </div>
  );
}
