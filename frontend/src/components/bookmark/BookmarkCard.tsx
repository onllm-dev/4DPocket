import { Link } from "react-router-dom";
import { Star, Clock, GitFork, MessageSquare, Eye, ArrowUp, Hash } from "lucide-react";
import { timeAgo } from "@/lib/utils";
import { useUpdateItem } from "@/hooks/use-items";
import { PlatformIcon } from "@/components/common/PlatformIcon";

interface BookmarkCardProps {
  item: {
    id: string;
    title: string | null;
    description: string | null;
    url: string | null;
    source_platform: string;
    item_type: string;
    summary: string | null;
    media: Array<{ type: string; url?: string; role: string; local_path?: string }>;
    is_favorite: boolean;
    created_at: string;
    item_metadata?: Record<string, unknown>;
    tags?: Array<{ id: string; name: string; color?: string | null }>;
  };
  variant?: "grid" | "list" | "compact";
}

function CardTags({ tags }: { tags?: Array<{ id: string; name: string; color?: string | null }> }) {
  if (!tags || tags.length === 0) return null;
  const shown = tags.slice(0, 3);
  const remaining = tags.length - shown.length;
  return (
    <div className="flex items-center gap-1 mt-1.5 flex-wrap">
      {shown.map((t) => (
        <span
          key={t.id}
          className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] bg-sky-50 dark:bg-sky-900/20 text-sky-600 dark:text-sky-400"
        >
          <Hash className="w-2.5 h-2.5" />
          {t.name}
        </span>
      ))}
      {remaining > 0 && (
        <span className="text-[10px] text-gray-400">+{remaining}</span>
      )}
    </div>
  );
}

function fmt(n: unknown): string {
  const num = Number(n);
  if (isNaN(num)) return String(n);
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}k`;
  return String(num);
}

function PlatformMeta({ platform, metadata }: { platform: string; metadata?: Record<string, unknown> }) {
  if (!metadata) return null;
  const p = platform.toLowerCase();

  if (p === "github") {
    const stars = metadata.stars ?? metadata.stargazers_count;
    const forks = metadata.forks ?? metadata.forks_count;
    const lang = metadata.language;
    if (!stars && !lang) return null;
    return (
      <div className="flex items-center gap-2.5 text-[10px] text-gray-500 dark:text-gray-400 mt-1.5">
        {lang ? <span className="bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 px-1.5 py-0.5 rounded">{String(lang)}</span> : null}
        {stars != null && <span className="inline-flex items-center gap-0.5"><Star className="w-3 h-3" />{fmt(stars)}</span>}
        {forks != null && <span className="inline-flex items-center gap-0.5"><GitFork className="w-3 h-3" />{fmt(forks)}</span>}
      </div>
    );
  }

  if (p === "reddit") {
    const score = metadata.score ?? metadata.upvotes;
    const comments = metadata.num_comments ?? metadata.comment_count;
    const subreddit = metadata.subreddit;
    if (!score && !subreddit) return null;
    return (
      <div className="flex items-center gap-2.5 text-[10px] text-gray-500 dark:text-gray-400 mt-1.5">
        {subreddit ? <span className="bg-orange-50 dark:bg-orange-900/20 text-orange-600 dark:text-orange-400 px-1.5 py-0.5 rounded">r/{String(subreddit)}</span> : null}
        {score != null && <span className="inline-flex items-center gap-0.5"><ArrowUp className="w-3 h-3" />{fmt(score)}</span>}
        {comments != null && <span className="inline-flex items-center gap-0.5"><MessageSquare className="w-3 h-3" />{fmt(comments)}</span>}
      </div>
    );
  }

  if (p === "youtube") {
    const channel = metadata.channel ?? metadata.channel_name ?? metadata.uploader;
    const views = metadata.view_count ?? metadata.views;
    if (!channel && !views) return null;
    return (
      <div className="flex items-center gap-2.5 text-[10px] text-gray-500 dark:text-gray-400 mt-1.5">
        {channel ? <span className="truncate max-w-[120px]">{String(channel)}</span> : null}
        {views != null && <span className="inline-flex items-center gap-0.5"><Eye className="w-3 h-3" />{fmt(views)}</span>}
      </div>
    );
  }

  if (p === "twitter") {
    const author = metadata.author ?? metadata.username;
    if (!author) return null;
    return (
      <div className="flex items-center gap-2 text-[10px] text-gray-500 dark:text-gray-400 mt-1.5">
        <span>@{String(author).replace(/^@/, "")}</span>
      </div>
    );
  }

  const author = metadata.author ?? metadata.author_name ?? metadata.by;
  if (!author) return null;
  return (
    <div className="flex items-center gap-2 text-[10px] text-gray-500 dark:text-gray-400 mt-1.5">
      <span className="truncate max-w-[150px]">{String(author)}</span>
    </div>
  );
}

export function BookmarkCard({ item, variant = "grid" }: BookmarkCardProps) {
  const updateItem = useUpdateItem();
  const thumbMedia = item.media?.find((m) => m.role === "thumbnail");
  const thumbUrl = thumbMedia?.url;
  // LinkedIn blocks hotlinking - proxy those images through backend
  const needsProxy = thumbUrl && (
    thumbUrl.includes("licdn.com") || thumbUrl.includes("linkedin.com")
  );
  const thumbnail = thumbMedia?.local_path
    ? `/api/v1/items/${item.id}/media/${thumbMedia.local_path}`
    : needsProxy
    ? `/api/v1/items/${item.id}/media-proxy?url=${encodeURIComponent(thumbUrl)}`
    : thumbUrl || undefined;

  const toggleFavorite = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    updateItem.mutate({ id: item.id, is_favorite: !item.is_favorite });
  };

  if (variant === "compact") {
    return (
      <Link
        to={`/item/${item.id}`}
        className="flex items-center gap-3 py-2.5 px-3 rounded-xl hover:bg-sky-50/50 dark:hover:bg-gray-800/50 transition-all duration-200 cursor-pointer group"
      >
        <PlatformIcon platform={item.source_platform} className="w-4 h-4" />
        <span className="text-sm truncate flex-1 text-gray-700 dark:text-gray-300">
          {item.title || item.url || "Untitled"}
        </span>
        <span className="text-xs text-gray-400 flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {timeAgo(item.created_at)}
        </span>
      </Link>
    );
  }

  if (variant === "list") {
    return (
      <Link
        to={`/item/${item.id}`}
        className="flex items-center gap-4 p-4 rounded-2xl border border-gray-200/80 dark:border-gray-800 bg-white dark:bg-gray-900 hover:shadow-lg hover:shadow-sky-100/50 dark:hover:shadow-sky-900/20 hover:border-sky-200 dark:hover:border-sky-800 hover:-translate-y-0.5 transition-all duration-300 cursor-pointer group"
      >
        {thumbnail ? (
          <img src={thumbnail} alt="" loading="lazy" className="w-16 h-16 rounded-xl object-cover flex-shrink-0" />
        ) : (
          <div className="w-16 h-16 rounded-xl bg-sky-50 dark:bg-sky-950 flex items-center justify-center flex-shrink-0">
            <PlatformIcon platform={item.source_platform} className="w-6 h-6" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <PlatformIcon platform={item.source_platform} className="w-3.5 h-3.5" />
            <span className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">{item.source_platform === "generic" ? "Web" : item.source_platform}</span>
          </div>
          <h3 className="font-semibold text-sm truncate text-gray-900 dark:text-gray-100 group-hover:text-[#0096C7] dark:group-hover:text-sky-400 transition-colors">
            {item.title || item.url || "Untitled"}
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
            {item.summary || item.description || ""}
          </p>
          <PlatformMeta platform={item.source_platform} metadata={item.item_metadata} />
          <CardTags tags={item.tags} />
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <button onClick={toggleFavorite} aria-label="Toggle favorite" className="p-1.5 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer">
            <Star className={`w-4 h-4 ${item.is_favorite ? "fill-[#FCD34D] text-[#FCD34D]" : "text-gray-300 dark:text-gray-600"}`} />
          </button>
          <span className="text-xs text-gray-400 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {timeAgo(item.created_at)}
          </span>
        </div>
      </Link>
    );
  }

  // Grid variant (default)
  return (
    <Link
      to={`/item/${item.id}`}
      className="flex flex-col rounded-2xl border border-gray-200/80 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden hover:shadow-lg hover:shadow-sky-100/50 dark:hover:shadow-sky-900/20 hover:border-sky-200 dark:hover:border-sky-800 hover:-translate-y-0.5 transition-all duration-300 cursor-pointer group"
    >
      {thumbnail ? (
        <div className="aspect-video bg-gray-100 dark:bg-gray-800 overflow-hidden">
          <img src={thumbnail} alt="" loading="lazy" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
        </div>
      ) : (
        <div className="aspect-video bg-gradient-to-br from-sky-50 to-sky-100 dark:from-sky-950 dark:to-gray-900 flex items-center justify-center">
          <PlatformIcon platform={item.source_platform} className="w-10 h-10" />
        </div>
      )}
      <div className="p-4 flex-1 flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <PlatformIcon platform={item.source_platform} className="w-3.5 h-3.5" />
            <span className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">{item.source_platform === "generic" ? "Web" : item.source_platform}</span>
          </div>
          <button onClick={toggleFavorite} aria-label="Toggle favorite" className="p-1 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer">
            <Star className={`w-4 h-4 ${item.is_favorite ? "fill-[#FCD34D] text-[#FCD34D]" : "text-gray-300 dark:text-gray-600 group-hover:text-gray-400"}`} />
          </button>
        </div>
        <h3 className="font-semibold text-sm line-clamp-2 mb-1 text-gray-900 dark:text-gray-100 group-hover:text-[#0096C7] dark:group-hover:text-sky-400 transition-colors">
          {item.title || item.url || "Untitled"}
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 flex-1">
          {item.summary || item.description || ""}
        </p>
        <PlatformMeta platform={item.source_platform} metadata={item.item_metadata} />
        <CardTags tags={item.tags} />
        <div className="flex items-center gap-1 mt-2 text-xs text-gray-400">
          <Clock className="w-3 h-3" />
          {timeAgo(item.created_at)}
        </div>
      </div>
    </Link>
  );
}
