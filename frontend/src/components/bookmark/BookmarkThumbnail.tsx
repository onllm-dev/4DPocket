import { useState } from "react";
import { Play } from "lucide-react";

import { PlatformIcon } from "@/components/common/PlatformIcon";

interface MediaItem {
  type?: string;
  url?: string;
  role?: string;
  local_path?: string;
}

interface Props {
  itemId: string;
  itemType?: string;
  sourcePlatform: string;
  url?: string | null;
  faviconUrl?: string | null;
  media?: MediaItem[];
  metadata?: Record<string, unknown>;
  // Visual shape
  shape: "aspect-video" | "square-16" | "square-24";
  iconSize: string;
}

// Resolve the best thumbnail URL we have, with a proxy fallback for
// platforms that block hotlinking (LinkedIn, Reddit previews). If the
// thumbnail 404s at render time we swap for the platform-icon state.
function resolveThumbnail(itemId: string, media?: MediaItem[]): string | undefined {
  const thumbMedia =
    media?.find((m) => m.role === "thumbnail" && m.local_path) ||
    media?.find((m) => m.role === "thumbnail") ||
    // Some processors emit the thumbnail with role="content" when no
    // explicit thumbnail was found (e.g. Reddit image posts).
    media?.find((m) => m.role === "content" && m.type === "image");

  if (!thumbMedia) return undefined;

  if (thumbMedia.local_path) {
    return `/api/v1/items/${itemId}/media/${thumbMedia.local_path}`;
  }
  const rawUrl = thumbMedia.url?.replaceAll("&amp;", "&");
  if (!rawUrl) return undefined;

  const hotlinkBlocked =
    rawUrl.includes("licdn.com") ||
    rawUrl.includes("linkedin.com") ||
    rawUrl.includes("preview.redd.it") ||
    rawUrl.includes("i.redd.it") ||
    rawUrl.includes("scontent") || // Instagram / Threads CDN
    rawUrl.includes("fbcdn.net"); // Meta CDN
  if (hotlinkBlocked) {
    return `/api/v1/items/${itemId}/media-proxy?url=${encodeURIComponent(rawUrl)}`;
  }
  return rawUrl;
}

function formatDuration(seconds: unknown): string | undefined {
  const n = Number(seconds);
  if (!Number.isFinite(n) || n <= 0) return undefined;
  const h = Math.floor(n / 3600);
  const m = Math.floor((n % 3600) / 60);
  const s = Math.floor(n % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function shapeClass(shape: Props["shape"]): string {
  switch (shape) {
    case "aspect-video":
      return "aspect-video";
    case "square-16":
      return "w-16 h-16 rounded-xl flex-shrink-0";
    case "square-24":
      return "w-24 h-24 rounded-xl flex-shrink-0";
  }
}

// Fallback tile — platform icon on a soft gradient. Used when no
// thumbnail is available OR the image failed to load.
function FallbackTile({
  sourcePlatform,
  url,
  faviconUrl,
  iconSize,
  shape,
}: Pick<Props, "sourcePlatform" | "url" | "faviconUrl" | "iconSize" | "shape">) {
  const bg =
    shape === "aspect-video"
      ? "bg-gradient-to-br from-sky-50 to-sky-100 dark:from-sky-950 dark:to-gray-900"
      : "bg-sky-50 dark:bg-sky-950";
  return (
    <div className={`${shapeClass(shape)} ${bg} flex items-center justify-center overflow-hidden`}>
      <PlatformIcon
        platform={sourcePlatform}
        url={url ?? undefined}
        faviconUrl={faviconUrl ?? undefined}
        className={iconSize}
      />
    </div>
  );
}

export function BookmarkThumbnail({
  itemId,
  itemType,
  sourcePlatform,
  url,
  faviconUrl,
  media,
  metadata,
  shape,
  iconSize,
}: Props) {
  const [loadError, setLoadError] = useState(false);
  const thumbnail = resolveThumbnail(itemId, media);
  const isVideo = itemType === "video" || Boolean(media?.some((m) => m.type === "video"));
  const duration = formatDuration(metadata?.duration);

  if (!thumbnail || loadError) {
    return (
      <FallbackTile
        sourcePlatform={sourcePlatform}
        url={url}
        faviconUrl={faviconUrl}
        iconSize={iconSize}
        shape={shape}
      />
    );
  }

  return (
    <div className={`${shapeClass(shape)} bg-gray-100 dark:bg-gray-800 overflow-hidden relative`}>
      <img
        src={thumbnail}
        alt=""
        loading="lazy"
        className="w-full h-full object-cover"
        onError={() => setLoadError(true)}
      />
      {isVideo && (
        // Play-button overlay for video items. Size-adaptive so it
        // doesn't dominate small square thumbnails.
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div
            className={
              shape === "aspect-video"
                ? "bg-black/55 rounded-full p-2.5"
                : "bg-black/55 rounded-full p-1"
            }
          >
            <Play
              className={
                shape === "aspect-video"
                  ? "w-5 h-5 text-white fill-white"
                  : "w-3 h-3 text-white fill-white"
              }
            />
          </div>
        </div>
      )}
      {duration && (
        <span className="absolute bottom-1 right-1 px-1.5 py-0.5 bg-black/75 text-white text-[10px] font-medium rounded">
          {duration}
        </span>
      )}
    </div>
  );
}
