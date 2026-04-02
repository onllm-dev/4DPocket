import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Star,
  Archive,
  Trash2,
  ExternalLink,
  Clock,
  Play,
  GitBranch,
  MessageSquare,
  Globe,
  Newspaper,
  BookOpen,
  Hash,
  Camera,
  AlertCircle,
} from "lucide-react";
import { useItem, useUpdateItem, useDeleteItem } from "@/hooks/use-items";
import { formatDate } from "@/lib/utils";

function getPlatformIcon(platform: string) {
  const icons: Record<string, React.ReactNode> = {
    youtube: <Play className="h-4 w-4" />,
    reddit: <MessageSquare className="h-4 w-4" />,
    github: <GitBranch className="h-4 w-4" />,
    twitter: <Hash className="h-4 w-4" />,
    hackernews: <Newspaper className="h-4 w-4" />,
    medium: <BookOpen className="h-4 w-4" />,
    substack: <Camera className="h-4 w-4" />,
  };
  return icons[platform] ?? <Globe className="h-4 w-4" />;
}

export default function ItemDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: item, isLoading, isError } = useItem(id ?? "");
  const updateItem = useUpdateItem();
  const deleteItem = useDeleteItem();

  if (isLoading) {
    return (
      <div className="animate-fade-in p-6 max-w-3xl mx-auto space-y-4">
        <div className="h-6 w-24 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg" />
        <div className="h-64 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg" />
        <div className="h-8 w-2/3 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg" />
        <div className="h-32 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg" />
      </div>
    );
  }

  if (isError || !item) {
    return (
      <div className="animate-fade-in p-6 max-w-3xl mx-auto text-center py-16">
        <AlertCircle className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
        <p className="text-gray-600 dark:text-gray-400 text-lg">
          Item not found.
        </p>
        <button
          onClick={() => navigate(-1)}
          className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm text-sky-600 hover:underline cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" />
          Go back
        </button>
      </div>
    );
  }

  const thumbnail = item.media?.find((m) => m.role === "thumbnail")?.url;
  const tags = Array.isArray(
    (item.item_metadata as Record<string, unknown>)?.tags
  )
    ? ((item.item_metadata as Record<string, unknown>).tags as string[])
    : [];

  const handleDelete = async () => {
    if (!confirm("Delete this item?")) return;
    await deleteItem.mutateAsync(item.id);
    navigate(-1);
  };

  const handleToggleFavorite = () => {
    updateItem.mutate({ id: item.id, is_favorite: !item.is_favorite });
  };

  const handleArchive = () => {
    updateItem.mutate({ id: item.id, is_archived: !item.is_archived });
  };

  return (
    <div className="animate-fade-in p-6 max-w-3xl mx-auto">
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 mb-6 p-2 -ml-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-all duration-200 cursor-pointer"
      >
        <ArrowLeft className="h-4 w-4" />
        Back
      </button>

      {thumbnail ? (
        <img
          src={thumbnail}
          alt=""
          className="w-full max-h-64 object-cover rounded-xl mb-6"
        />
      ) : (
        <div className="w-full h-40 rounded-xl mb-6 bg-gradient-to-br from-sky-100 to-sky-50 dark:from-sky-900/30 dark:to-gray-900 flex items-center justify-center">
          {getPlatformIcon(item.source_platform)}
        </div>
      )}

      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sky-600">
              {getPlatformIcon(item.source_platform)}
            </span>
            <span className="text-xs uppercase tracking-wider text-gray-600 dark:text-gray-400 font-medium bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full">
              {item.source_platform}
            </span>
            <span className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400">
              <Clock className="h-3 w-3" />
              {formatDate(item.created_at)}
            </span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {item.title || item.url || "Untitled"}
          </h1>
        </div>

        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={handleToggleFavorite}
            title={item.is_favorite ? "Unfavorite" : "Favorite"}
            className={`p-2.5 rounded-lg hover:shadow-md transition-all duration-200 cursor-pointer ${
              item.is_favorite
                ? "bg-amber-50 dark:bg-amber-900/20 text-amber-500"
                : "hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400"
            }`}
          >
            <Star
              className="h-5 w-5"
              fill={item.is_favorite ? "currentColor" : "none"}
            />
          </button>
          <button
            onClick={handleArchive}
            title={item.is_archived ? "Unarchive" : "Archive"}
            className={`p-2.5 rounded-lg hover:shadow-md transition-all duration-200 cursor-pointer ${
              item.is_archived
                ? "bg-sky-50 dark:bg-sky-900/20 text-sky-600"
                : "hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400"
            }`}
          >
            <Archive className="h-5 w-5" />
          </button>
          <button
            onClick={handleDelete}
            title="Delete"
            className="p-2.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-red-400 hover:shadow-md transition-all duration-200 cursor-pointer"
          >
            <Trash2 className="h-5 w-5" />
          </button>
        </div>
      </div>

      {item.url && (
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-sky-600 hover:underline mb-6 truncate max-w-full cursor-pointer"
        >
          <ExternalLink className="h-3.5 w-3.5 flex-shrink-0" />
          {item.url}
        </a>
      )}

      {item.summary && (
        <div className="rounded-xl border border-sky-200 dark:border-sky-800 bg-sky-50 dark:bg-sky-900/20 p-4 mb-6">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-sky-600 mb-2">
            AI Summary
          </h2>
          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
            {item.summary}
          </p>
        </div>
      )}

      {item.content && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5 mb-6">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-3">
            Content
          </h2>
          <div
            className="prose prose-sm dark:prose-invert max-w-none text-gray-700 dark:text-gray-300 leading-relaxed"
            dangerouslySetInnerHTML={{ __html: item.content }}
          />
        </div>
      )}

      {Object.keys(item.item_metadata ?? {}).length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5 mb-6">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-3">
            Metadata
          </h2>
          <div className="space-y-2">
            {Object.entries(item.item_metadata).map(([key, val]) => (
              <div key={key} className="flex gap-3 text-sm">
                <span className="text-gray-600 dark:text-gray-400 font-medium w-32 shrink-0 capitalize">
                  {key.replace(/_/g, " ")}
                </span>
                <span className="text-gray-700 dark:text-gray-300 truncate">
                  {String(val)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {tags.length > 0 && (
        <div className="mb-6">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-3">
            Tags
          </h2>
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => (
              <span
                key={tag}
                className="px-2.5 py-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 rounded-full text-xs"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-8 border-t border-gray-200 dark:border-gray-800 pt-6">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-3">
          Related Items
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 italic">
          Coming soon...
        </p>
      </div>
    </div>
  );
}
