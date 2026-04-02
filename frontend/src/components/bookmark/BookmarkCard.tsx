import { Link } from "react-router-dom";
import { Star, Clock, Globe, MessageSquare, Camera, FileText as FileTextIcon, Music, Newspaper, Code, Play, GitBranch } from "lucide-react";
import { timeAgo } from "@/lib/utils";
import { useUpdateItem } from "@/hooks/use-items";

// Platform icon map using Lucide
const PLATFORM_ICONS: Record<string, React.ElementType> = {
  youtube: Play,
  github: GitBranch,
  reddit: MessageSquare,
  twitter: Globe, // X doesn't have a Lucide icon, use Globe
  instagram: Camera,
  hackernews: Newspaper,
  stackoverflow: Code,
  medium: FileTextIcon,
  substack: Newspaper,
  spotify: Music,
  generic: Globe,
};

interface BookmarkCardProps {
  item: {
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
  variant?: "grid" | "list" | "compact";
}

export function BookmarkCard({ item, variant = "grid" }: BookmarkCardProps) {
  const updateItem = useUpdateItem();
  const thumbnail = item.media?.find((m) => m.role === "thumbnail")?.url;
  const PlatformIcon = PLATFORM_ICONS[item.source_platform] || Globe;

  const toggleFavorite = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    updateItem.mutate({ id: item.id, is_favorite: !item.is_favorite });
  };

  if (variant === "compact") {
    return (
      <Link
        to={`/item/${item.id}`}
        className="flex items-center gap-3 py-2.5 px-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-all duration-200 cursor-pointer group"
      >
        <PlatformIcon className="w-4 h-4 text-gray-400 group-hover:text-sky-500 transition-colors" />
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
        className="flex items-center gap-4 p-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 hover:shadow-md hover:border-sky-200 dark:hover:border-sky-800 transition-all duration-200 cursor-pointer group"
      >
        {thumbnail ? (
          <img src={thumbnail} alt="" className="w-16 h-16 rounded-lg object-cover flex-shrink-0" />
        ) : (
          <div className="w-16 h-16 rounded-lg bg-sky-50 dark:bg-sky-950 flex items-center justify-center flex-shrink-0">
            <PlatformIcon className="w-6 h-6 text-sky-500" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <PlatformIcon className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">{item.source_platform}</span>
          </div>
          <h3 className="font-semibold text-sm truncate text-gray-900 dark:text-gray-100 group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors">
            {item.title || item.url || "Untitled"}
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
            {item.summary || item.description || ""}
          </p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <button onClick={toggleFavorite} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer">
            <Star className={`w-4 h-4 ${item.is_favorite ? "fill-amber-400 text-amber-400" : "text-gray-300 dark:text-gray-600"}`} />
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
      className="flex flex-col rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden hover:shadow-md hover:border-sky-200 dark:hover:border-sky-800 transition-all duration-200 cursor-pointer group"
    >
      {thumbnail ? (
        <div className="aspect-video bg-gray-100 dark:bg-gray-800 overflow-hidden">
          <img src={thumbnail} alt="" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
        </div>
      ) : (
        <div className="aspect-video bg-gradient-to-br from-sky-50 to-sky-100 dark:from-sky-950 dark:to-gray-900 flex items-center justify-center">
          <PlatformIcon className="w-10 h-10 text-sky-300 dark:text-sky-700" />
        </div>
      )}
      <div className="p-4 flex-1 flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <PlatformIcon className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">{item.source_platform}</span>
          </div>
          <button onClick={toggleFavorite} className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer">
            <Star className={`w-4 h-4 ${item.is_favorite ? "fill-amber-400 text-amber-400" : "text-gray-300 dark:text-gray-600 group-hover:text-gray-400"}`} />
          </button>
        </div>
        <h3 className="font-semibold text-sm line-clamp-2 mb-1 text-gray-900 dark:text-gray-100 group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors">
          {item.title || item.url || "Untitled"}
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 flex-1">
          {item.summary || item.description || ""}
        </p>
        <div className="flex items-center gap-1 mt-3 text-xs text-gray-400">
          <Clock className="w-3 h-3" />
          {timeAgo(item.created_at)}
        </div>
      </div>
    </Link>
  );
}
