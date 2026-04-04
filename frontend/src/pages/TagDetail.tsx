import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Hash, Sparkles } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { BookmarkCard } from "@/components/bookmark/BookmarkCard";

interface TagInfo {
  id: string;
  name: string;
  slug: string;
  color: string | null;
  usage_count: number;
  ai_generated: boolean;
}

interface Item {
  id: string;
  item_type: string;
  source_platform: string;
  url: string | null;
  title: string | null;
  description: string | null;
  content: string | null;
  summary: string | null;
  media: Array<{ type: string; url: string; role: string; local_path?: string }>;
  item_metadata: Record<string, unknown>;
  is_favorite: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

interface SimilarTag {
  tag_a: { id: string; name: string; usage_count: number };
  tag_b: { id: string; name: string; usage_count: number };
  similarity: number;
}

export default function TagDetail() {
  const { id } = useParams<{ id: string }>();
  const tagId = id ?? "";

  const { data: tags } = useQuery<TagInfo[]>({
    queryKey: ["tags"],
    queryFn: () => api.get("/api/v1/tags"),
  });
  const tag = tags?.find((t) => t.id === tagId);

  const { data: items, isLoading } = useQuery<Item[]>({
    queryKey: ["tag-items", tagId],
    queryFn: () => api.get(`/api/v1/tags/${tagId}/items?limit=100`),
    enabled: !!tagId,
  });

  const { data: similarSuggestions } = useQuery<SimilarTag[]>({
    queryKey: ["tag-merge-suggestions"],
    queryFn: () => api.get("/api/v1/tags/suggestions/merge"),
  });

  // Filter similar tags that involve this tag
  const similarTags = similarSuggestions?.filter(
    (s) => s.tag_a.id === tagId || s.tag_b.id === tagId
  ).map((s) => s.tag_a.id === tagId ? s.tag_b : s.tag_a) ?? [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-sky-600 text-lg">Loading...</div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 animate-fade-in">
      <Link
        to="/tags"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        All Tags
      </Link>

      <div className="flex items-center gap-3 mb-6">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center"
          style={{ backgroundColor: tag?.color ? `${tag.color}20` : "rgb(14 165 233 / 0.1)" }}
        >
          <Hash className="w-5 h-5" style={{ color: tag?.color || "#0ea5e9" }} />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {tag?.name || "Tag"}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {items?.length ?? 0} item{(items?.length ?? 0) !== 1 ? "s" : ""}
            {tag?.ai_generated && (
              <span className="ml-2 inline-flex items-center gap-1 text-sky-500">
                <Sparkles className="w-3 h-3" /> AI generated
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Similar tags */}
      {similarTags.length > 0 && (
        <div className="mb-6 p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/50">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
            Similar Tags
          </h2>
          <div className="flex flex-wrap gap-2">
            {similarTags.map((st) => (
              <Link
                key={st.id}
                to={`/tags/${st.id}`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-sky-50 dark:hover:bg-sky-900/20 hover:text-sky-600 transition-colors"
              >
                <Hash className="w-3 h-3" />
                {st.name}
                <span className="text-gray-400">({st.usage_count})</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Items */}
      {items && items.length > 0 ? (
        <div className="flex flex-col gap-3">
          {items.map((item) => (
            <BookmarkCard key={item.id} item={item} variant="list" />
          ))}
        </div>
      ) : (
        <div className="text-center py-16 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <Hash className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-700 dark:text-gray-300 text-lg font-medium mb-1">
            No items with this tag
          </p>
          <p className="text-sm text-gray-400 dark:text-gray-500">
            Items tagged with this tag will appear here
          </p>
        </div>
      )}
    </div>
  );
}
