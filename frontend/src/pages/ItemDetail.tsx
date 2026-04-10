import { useState, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  ArrowLeft,
  Star,
  Archive,
  Trash2,
  ExternalLink,
  Clock,
  AlertCircle,
  Share2,
  Send,
  Eye,
  ThumbsUp,
  GitFork,
  MessageSquare,
  User,
  Calendar,
  Hash,
  Play,
  Repeat2,
  Pencil,
  FolderPlus,
  BookOpen,
  BookMarked,
  LinkIcon,
  Plus,
  X,
  Check,
  CircleDot,
  CircleCheck,
  GitMerge,
  GitPullRequest,
  Scale,
  Tag,
  FileCode,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import { PlatformIcon } from "@/components/common/PlatformIcon";
import ContentRenderer from "@/components/content/ContentRenderer";
import TextHighlighter from "@/components/content/TextHighlighter";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useItem, useUpdateItem, useDeleteItem } from "@/hooks/use-items";
import { useCollections, useAddItemToCollection } from "@/hooks/use-collections";
import { useToggleReadingList, useMarkAsRead } from "@/hooks/use-reading-list";
import { useHighlights } from "@/hooks/use-highlights";
import { useItemLinks, useAddItemLink, useRemoveItemLink } from "@/hooks/use-item-links";
import { formatDate } from "@/lib/utils";
import { ShareDialog } from "@/components/sharing/ShareDialog";
import { EditBookmarkForm } from "@/components/bookmark/BookmarkForm";

// Fields to always hide from metadata display
const HIDDEN_METADATA_KEYS = new Set([
  "raw_content",
  "og_image",
  "og_description",
  "og_title",
  "og_url",
  "og_type",
  "og_site_name",
  "tags",
  "thumbnail_url",
  "screenshot_url",
]);

function formatNumber(n: unknown): string {
  const num = typeof n === "number" ? n : Number(n);
  if (isNaN(num)) return String(n);
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
  return String(num);
}

function formatDuration(seconds: unknown): string {
  const s = typeof seconds === "number" ? seconds : Number(seconds);
  if (isNaN(s)) return String(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

interface MetaBadgeProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  colorClass?: string;
}

function MetaBadge({ icon, label, value, colorClass = "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300" }: MetaBadgeProps) {
  return (
    <div
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium ${colorClass}`}
      title={label}
    >
      {icon}
      <span>{value}</span>
    </div>
  );
}

interface PlatformMetadataProps {
  platform: string;
  metadata: Record<string, unknown>;
}

function YouTubeMetadata({ metadata }: { metadata: Record<string, unknown> }) {
  const durationRaw = metadata.duration ?? metadata.length_seconds;
  const channel = metadata.channel ?? metadata.channel_name ?? metadata.uploader;
  const viewsRaw = metadata.view_count ?? metadata.views;
  const likesRaw = metadata.like_count ?? metadata.likes;

  const channelStr = channel != null ? String(channel) : null;
  const durationStr = durationRaw != null ? formatDuration(durationRaw) : null;
  const viewsStr = viewsRaw != null ? formatNumber(viewsRaw) : null;
  const likesStr = likesRaw != null ? formatNumber(likesRaw) : null;

  return (
    <div className="flex flex-wrap gap-2 mt-1">
      {channelStr && (
        <MetaBadge
          icon={<User className="h-3.5 w-3.5" />}
          label="Channel"
          value={channelStr}
          colorClass="bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
        />
      )}
      {durationStr && (
        <MetaBadge
          icon={<Play className="h-3.5 w-3.5" />}
          label="Duration"
          value={durationStr}
          colorClass="bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
        />
      )}
      {viewsStr && (
        <MetaBadge
          icon={<Eye className="h-3.5 w-3.5" />}
          label="Views"
          value={viewsStr}
          colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
        />
      )}
      {likesStr && (
        <MetaBadge
          icon={<ThumbsUp className="h-3.5 w-3.5" />}
          label="Likes"
          value={likesStr}
          colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
        />
      )}
    </div>
  );
}

function GitHubMetadata({ metadata }: { metadata: Record<string, unknown> }) {
  const ghType = metadata.type as string | undefined;
  const ownerRaw = metadata.owner ?? metadata.author;
  const ownerStr = ownerRaw != null ? String(ownerRaw) : null;

  // Issue / PR fields
  const numberRaw = metadata.number;
  const stateRaw = metadata.state as string | undefined;
  const labels = Array.isArray(metadata.labels) ? (metadata.labels as string[]) : [];
  const commentCount = metadata.comment_count;
  const closedAt = metadata.closed_at as string | undefined;

  // Repo fields
  const starsRaw = metadata.stargazers_count ?? metadata.stars ?? metadata.star_count;
  const forksRaw = metadata.forks_count ?? metadata.forks;
  const languageRaw = metadata.language ?? metadata.primary_language;
  const licenseRaw = metadata.license;
  const topics = Array.isArray(metadata.topics) ? (metadata.topics as string[]) : [];
  const updatedAt = metadata.updated_at as string | undefined;
  const openIssues = metadata.open_issues;

  const starsStr = starsRaw != null ? formatNumber(starsRaw) : null;
  const forksStr = forksRaw != null ? formatNumber(forksRaw) : null;
  const languageStr = languageRaw != null ? String(languageRaw) : null;
  const licenseStr = licenseRaw != null ? String(licenseRaw) : null;

  // Detect content type
  const isIssue = ghType === "issue";
  const isPR = ghType === "pull";
  const isIssueOrPR = isIssue || isPR;

  // State badge colors
  const stateOpen = stateRaw === "open";
  const stateClosed = stateRaw === "closed";
  const stateMerged = stateRaw === "merged";

  const stateColor = stateMerged
    ? "bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300"
    : stateOpen
    ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300"
    : stateClosed
    ? "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300"
    : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300";

  const stateIcon = stateMerged ? (
    <GitMerge className="h-3.5 w-3.5" />
  ) : isPR ? (
    <GitPullRequest className="h-3.5 w-3.5" />
  ) : stateOpen ? (
    <CircleDot className="h-3.5 w-3.5" />
  ) : (
    <CircleCheck className="h-3.5 w-3.5" />
  );

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {ownerStr && (
          <MetaBadge
            icon={<User className="h-3.5 w-3.5" />}
            label="Owner"
            value={ownerStr}
            colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
          />
        )}

        {/* Issue/PR number and state */}
        {isIssueOrPR && numberRaw != null && (
          <MetaBadge
            icon={isPR ? <GitPullRequest className="h-3.5 w-3.5" /> : <CircleDot className="h-3.5 w-3.5" />}
            label={isPR ? "PR" : "Issue"}
            value={`${isPR ? "PR" : "Issue"} #${numberRaw}`}
            colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
          />
        )}

        {isIssueOrPR && stateRaw && (
          <MetaBadge
            icon={stateIcon}
            label="State"
            value={stateRaw.charAt(0).toUpperCase() + stateRaw.slice(1)}
            colorClass={stateColor}
          />
        )}

        {/* Repo: language with color dot */}
        {languageStr && (
          <MetaBadge
            icon={<FileCode className="h-3.5 w-3.5" />}
            label="Language"
            value={languageStr}
            colorClass="bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300"
          />
        )}

        {/* Stars */}
        {starsStr && (
          <MetaBadge
            icon={<Star className="h-3.5 w-3.5" />}
            label="Stars"
            value={starsStr}
            colorClass="bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300"
          />
        )}

        {/* Forks */}
        {forksStr && (
          <MetaBadge
            icon={<GitFork className="h-3.5 w-3.5" />}
            label="Forks"
            value={forksStr}
            colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
          />
        )}

        {/* License */}
        {licenseStr && licenseStr !== "null" && (
          <MetaBadge
            icon={<Scale className="h-3.5 w-3.5" />}
            label="License"
            value={licenseStr}
            colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
          />
        )}

        {/* Open issues count (repos) */}
        {openIssues != null && !isIssueOrPR && (
          <MetaBadge
            icon={<AlertTriangle className="h-3.5 w-3.5" />}
            label="Open Issues"
            value={formatNumber(openIssues)}
            colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
          />
        )}

        {/* Comment count (issues/PRs) */}
        {isIssueOrPR && commentCount != null && (
          <MetaBadge
            icon={<MessageSquare className="h-3.5 w-3.5" />}
            label="Comments"
            value={formatNumber(commentCount)}
            colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
          />
        )}

        {/* Closed date for issues/PRs */}
        {isIssueOrPR && closedAt && (
          <MetaBadge
            icon={<Calendar className="h-3.5 w-3.5" />}
            label="Closed"
            value={closedAt.slice(0, 10)}
            colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
          />
        )}

        {/* Last updated (repos) */}
        {updatedAt && !isIssueOrPR && (
          <MetaBadge
            icon={<Clock className="h-3.5 w-3.5" />}
            label="Updated"
            value={updatedAt.slice(0, 10)}
            colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
          />
        )}
      </div>

      {/* Labels (issues/PRs) */}
      {labels.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {labels.map((label) => (
            <span
              key={label}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700"
            >
              <Tag className="h-2.5 w-2.5" />
              {label}
            </span>
          ))}
        </div>
      )}

      {/* Topics (repos) */}
      {topics.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {topics.map((topic) => (
            <span
              key={topic}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400"
            >
              <Hash className="h-2.5 w-2.5" />
              {topic}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function RedditMetadata({ metadata }: { metadata: Record<string, unknown> }) {
  const subredditRaw = metadata.subreddit ?? metadata.subreddit_name;
  const scoreRaw = metadata.score ?? metadata.upvotes ?? metadata.ups;
  const commentsRaw = metadata.num_comments ?? metadata.comment_count ?? metadata.comments;

  const subredditStr = subredditRaw != null ? `r/${String(subredditRaw).replace(/^r\//, "")}` : null;
  const scoreStr = scoreRaw != null ? formatNumber(scoreRaw) : null;
  const commentsStr = commentsRaw != null ? formatNumber(commentsRaw) : null;

  return (
    <div className="flex flex-wrap gap-2 mt-1">
      {subredditStr && (
        <MetaBadge
          icon={<Hash className="h-3.5 w-3.5" />}
          label="Subreddit"
          value={subredditStr}
          colorClass="bg-orange-50 dark:bg-orange-900/20 text-orange-700 dark:text-orange-300"
        />
      )}
      {scoreStr && (
        <MetaBadge
          icon={<ThumbsUp className="h-3.5 w-3.5" />}
          label="Score"
          value={scoreStr}
          colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
        />
      )}
      {commentsStr && (
        <MetaBadge
          icon={<MessageSquare className="h-3.5 w-3.5" />}
          label="Comments"
          value={commentsStr}
          colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
        />
      )}
    </div>
  );
}

function TwitterMetadata({ metadata }: { metadata: Record<string, unknown> }) {
  const authorRaw = metadata.author ?? metadata.username ?? metadata.screen_name ?? metadata.user_name;
  const retweetsRaw = metadata.retweet_count ?? metadata.retweets;
  const likesRaw = metadata.favorite_count ?? metadata.like_count ?? metadata.likes;

  const authorStr = authorRaw != null ? `@${String(authorRaw).replace(/^@/, "")}` : null;
  const retweetsStr = retweetsRaw != null ? formatNumber(retweetsRaw) : null;
  const likesStr = likesRaw != null ? formatNumber(likesRaw) : null;

  return (
    <div className="flex flex-wrap gap-2 mt-1">
      {authorStr && (
        <MetaBadge
          icon={<User className="h-3.5 w-3.5" />}
          label="Author"
          value={authorStr}
          colorClass="bg-gray-100 dark:bg-gray-900 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700"
        />
      )}
      {retweetsStr && (
        <MetaBadge
          icon={<Repeat2 className="h-3.5 w-3.5" />}
          label="Retweets"
          value={retweetsStr}
          colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
        />
      )}
      {likesStr && (
        <MetaBadge
          icon={<ThumbsUp className="h-3.5 w-3.5" />}
          label="Likes"
          value={likesStr}
          colorClass="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
        />
      )}
    </div>
  );
}

function GenericMetadata({ metadata }: { metadata: Record<string, unknown> }) {
  const authorRaw = metadata.author ?? metadata.author_name ?? metadata.by;
  const publishDateRaw = metadata.published_at ?? metadata.publish_date ?? metadata.date ?? metadata.published;

  const authorStr = authorRaw != null ? String(authorRaw) : null;
  const publishDateStr = publishDateRaw != null ? String(publishDateRaw).slice(0, 10) : null;

  const displayed = new Set(["author", "author_name", "by", "published_at", "publish_date", "date", "published"]);
  const extras = Object.entries(metadata).filter(
    ([k, v]) =>
      !displayed.has(k) &&
      !HIDDEN_METADATA_KEYS.has(k) &&
      v != null &&
      String(v) !== "" &&
      String(v) !== "null" &&
      String(v) !== "undefined"
  );

  return (
    <div className="space-y-3">
      {(authorStr || publishDateStr) && (
        <div className="flex flex-wrap gap-2">
          {authorStr && (
            <MetaBadge
              icon={<User className="h-3.5 w-3.5" />}
              label="Author"
              value={authorStr}
            />
          )}
          {publishDateStr && (
            <MetaBadge
              icon={<Calendar className="h-3.5 w-3.5" />}
              label="Published"
              value={publishDateStr}
            />
          )}
        </div>
      )}
      {extras.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5">
          {extras.map(([key, val]) => {
            const strVal = typeof val === "object" ? JSON.stringify(val) : String(val);
            if (strVal.length > 300) return null;
            return (
              <div key={key} className="flex gap-3 text-sm py-0.5">
                <span className="text-gray-500 dark:text-gray-400 font-medium min-w-[110px] shrink-0 capitalize">
                  {key.replace(/_/g, " ")}
                </span>
                <span className="text-gray-700 dark:text-gray-300 truncate" title={strVal}>
                  {strVal.length > 100 ? strVal.slice(0, 100) + "…" : strVal}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function PlatformMetadata({ platform, metadata }: PlatformMetadataProps) {
  const p = platform.toLowerCase();
  if (p === "youtube") return <YouTubeMetadata metadata={metadata} />;
  if (p === "github") return <GitHubMetadata metadata={metadata} />;
  if (p === "reddit") return <RedditMetadata metadata={metadata} />;
  if (p === "twitter") return <TwitterMetadata metadata={metadata} />;
  return <GenericMetadata metadata={metadata} />;
}

// Platform colors for gradient placeholders
const PLATFORM_GRADIENTS: Record<string, string> = {
  youtube: "from-red-100 to-red-50 dark:from-red-900/30 dark:to-gray-900",
  github: "from-gray-200 to-gray-100 dark:from-gray-800/50 dark:to-gray-900",
  reddit: "from-orange-100 to-orange-50 dark:from-orange-900/30 dark:to-gray-900",
  twitter: "from-sky-100 to-sky-50 dark:from-sky-900/30 dark:to-gray-900",
  instagram: "from-purple-100 to-pink-50 dark:from-purple-900/30 dark:to-gray-900",
  linkedin: "from-blue-100 to-blue-50 dark:from-blue-900/30 dark:to-gray-900",
  hackernews: "from-orange-100 to-amber-50 dark:from-orange-900/30 dark:to-gray-900",
  medium: "from-gray-100 to-gray-50 dark:from-gray-800/50 dark:to-gray-900",
  substack: "from-orange-100 to-amber-50 dark:from-orange-900/30 dark:to-gray-900",
  spotify: "from-green-100 to-emerald-50 dark:from-green-900/30 dark:to-gray-900",
};

function getThumbnailGradient(platform: string): string {
  return PLATFORM_GRADIENTS[platform.toLowerCase()] ?? "from-sky-100 to-sky-50 dark:from-sky-900/30 dark:to-gray-900";
}


export default function ItemDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: item, isLoading, isError } = useItem(id ?? "");
  const updateItem = useUpdateItem();
  const deleteItem = useDeleteItem();
  const [shareOpen, setShareOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [collectionPickerOpen, setCollectionPickerOpen] = useState(false);
  const { data: collections } = useCollections();
  const addToCollection = useAddItemToCollection();
  const toggleReadingList = useToggleReadingList();
  const markAsRead = useMarkAsRead();
  const { data: highlights } = useHighlights(id);

  const commentInputRef = useRef<HTMLInputElement>(null);

  const { data: relatedItems } = useQuery<Array<{
    id: string;
    title: string;
    url: string | null;
    source_platform: string;
    score: number;
  }>>({
    queryKey: ["items", id, "related"],
    queryFn: () => api.get(`/api/v1/items/${id}/related`),
    enabled: !!id,
  });

  const { data: itemTags } = useQuery<Array<{
    tag_id: string;
    tag_name: string;
    tag_color: string | null;
    confidence: number;
    ai_generated: boolean;
  }>>({
    queryKey: ["items", id, "tags"],
    queryFn: () => api.get(`/api/v1/items/${id}/tags`),
    enabled: !!id,
  });

  const { data: comments } = useQuery<Array<{
    id: string;
    content: string;
    user_display_name: string;
    created_at: string;
  }>>({
    queryKey: ["items", id, "comments"],
    queryFn: () => api.get(`/api/v1/items/${id}/comments`),
    enabled: !!id,
  });

  const addComment = useMutation({
    mutationFn: (content: string) =>
      api.post(`/api/v1/items/${id}/comments`, { content }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["items", id, "comments"] });
      setCommentText("");
    },
  });

  const handleAddComment = () => {
    const trimmed = commentText.trim();
    if (!trimmed) return;
    addComment.mutate(trimmed);
  };

  const [reprocessing, setReprocessing] = useState(false);
  const handleReprocess = async () => {
    if (!item?.url) return;
    setReprocessing(true);
    try {
      await api.post(`/api/v1/items/${item.id}/reprocess`);
    } catch {}
    setTimeout(() => setReprocessing(false), 2000);
  };

  if (isLoading) {
    return (
      <div className="animate-fade-in max-w-5xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div className="h-8 w-16 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-xl" />
          <div className="h-10 w-48 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-xl" />
        </div>
        <div className="aspect-video rounded-2xl animate-pulse bg-gray-100 dark:bg-gray-800" />
        <div className="space-y-2">
          <div className="flex gap-2">
            <div className="h-4 w-16 animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
            <div className="h-4 w-24 animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
          </div>
          <div className="h-7 w-3/4 animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-4 w-1/2 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
        </div>
        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 p-5 space-y-2">
          <div className="h-3 w-20 animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-4 w-full animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
          <div className="h-4 w-5/6 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
        </div>
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

  const thumbMedia = item.media?.find((m) => m.role === "thumbnail");
  const thumbUrl = thumbMedia?.url?.replaceAll("&amp;", "&");
  const needsProxy = thumbUrl && (
    thumbUrl.includes("licdn.com") ||
    thumbUrl.includes("linkedin.com") ||
    thumbUrl.includes("preview.redd.it")
  );
  const thumbnail = thumbMedia?.local_path
    ? `/api/v1/items/${item.id}/media/${thumbMedia.local_path}`
    : needsProxy
    ? `/api/v1/items/${item.id}/media-proxy?url=${encodeURIComponent(thumbUrl)}`
    : thumbUrl || undefined;
  const tags = itemTags ?? [];
  const isYouTube = item.source_platform.toLowerCase() === "youtube";
  const metadata = item.item_metadata ?? {};

  // Check if metadata has anything worth showing after filtering
  const hasDisplayableMetadata = Object.keys(metadata).some(
    (k) => !HIDDEN_METADATA_KEYS.has(k) && metadata[k] != null && String(metadata[k]) !== ""
  );

  const handleDelete = async () => {
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
    <div className="animate-fade-in max-w-5xl mx-auto space-y-6">
      {/* Back + Actions bar */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate(-1)}
          aria-label="Go back"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 p-2 -ml-2 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 transition-all duration-200 cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
        <div className="flex items-center gap-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-1 shadow-sm">
          <button
            onClick={handleToggleFavorite}
            aria-label={item.is_favorite ? "Unfavorite" : "Favorite"}
            title={item.is_favorite ? "Unfavorite" : "Favorite"}
            className={`p-2 rounded-lg transition-all duration-200 cursor-pointer ${
              item.is_favorite
                ? "bg-amber-50 dark:bg-amber-900/20 text-amber-500"
                : "hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400"
            }`}
          >
            <Star className="h-4 w-4" fill={item.is_favorite ? "currentColor" : "none"} />
          </button>
          <button
            onClick={handleArchive}
            aria-label={item.is_archived ? "Unarchive" : "Archive"}
            className={`p-2 rounded-lg transition-all duration-200 cursor-pointer ${
              item.is_archived
                ? "bg-sky-50 dark:bg-sky-900/20 text-sky-600"
                : "hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400"
            }`}
          >
            <Archive className="h-4 w-4" />
          </button>
          <button onClick={() => setEditOpen(true)} aria-label="Edit" className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-sky-600 transition-all duration-200 cursor-pointer">
            <Pencil className="h-4 w-4" />
          </button>
          <button onClick={() => setCollectionPickerOpen((p) => !p)} aria-label="Add to Collection" className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-sky-600 transition-all duration-200 cursor-pointer">
            <FolderPlus className="h-4 w-4" />
          </button>
          <button onClick={() => setShareOpen(true)} aria-label="Share" className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-sky-600 transition-all duration-200 cursor-pointer">
            <Share2 className="h-4 w-4" />
          </button>
          {item.url && (
            <button
              onClick={handleReprocess}
              disabled={reprocessing}
              aria-label="Refresh content"
              title="Re-fetch and reprocess content"
              className={`p-2 rounded-lg transition-all duration-200 cursor-pointer ${
                reprocessing
                  ? "bg-sky-50 dark:bg-sky-900/20 text-sky-600"
                  : "hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-sky-600"
              }`}
            >
              <RefreshCw className={`h-4 w-4 ${reprocessing ? "animate-spin" : ""}`} />
            </button>
          )}
          <button
            onClick={() => toggleReadingList.mutate({ id: item.id, type: "item", add: item.reading_status !== "reading_list" })}
            aria-label={item.reading_status === "reading_list" ? "Remove from Reading List" : "Add to Reading List"}
            title={item.reading_status === "reading_list" ? "Remove from Reading List" : "Add to Reading List"}
            className={`p-2 rounded-lg transition-all duration-200 cursor-pointer ${
              item.reading_status === "reading_list"
                ? "bg-sky-50 dark:bg-sky-900/20 text-sky-600"
                : "hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400"
            }`}
          >
            <BookOpen className="h-4 w-4" />
          </button>
          <div className="w-px h-5 bg-gray-200 dark:bg-gray-700 mx-0.5" />
          {confirmDelete ? (
            <div className="flex items-center gap-1 ml-1">
              <button onClick={handleDelete} aria-label="Confirm delete" className="p-2 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-500 transition-all duration-200 cursor-pointer">
                <Check className="h-4 w-4" />
              </button>
              <button onClick={() => setConfirmDelete(false)} aria-label="Cancel delete" className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 transition-all duration-200 cursor-pointer">
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <button onClick={() => setConfirmDelete(true)} aria-label="Delete" className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-500 transition-all duration-200 cursor-pointer">
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Collection picker dropdown */}
      {collectionPickerOpen && collections && (
        <div className="p-3 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Add to Collection</p>
          <div className="flex flex-wrap gap-2">
            {collections.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  addToCollection.mutate({ collectionId: c.id, itemIds: [item.id] });
                  setCollectionPickerOpen(false);
                }}
                className="px-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 hover:border-sky-300 dark:hover:border-sky-600 hover:bg-sky-50 dark:hover:bg-sky-900/20 transition-colors"
              >
                {c.name}
              </button>
            ))}
            {collections.length === 0 && (
              <p className="text-xs text-gray-400">No collections yet. Create one first.</p>
            )}
          </div>
        </div>
      )}

      {/* Hero thumbnail */}
      {thumbnail ? (
        <div className={isYouTube ? "relative w-full aspect-video rounded-2xl overflow-hidden shadow-lg" : "w-full"}>
          <img
            src={thumbnail}
            alt=""
            className={
              isYouTube
                ? "w-full h-full object-cover"
                : "w-full max-h-72 object-contain rounded-2xl bg-gray-100 dark:bg-gray-900"
            }
          />
        </div>
      ) : (
        <div
          className={`w-full rounded-2xl flex items-center justify-center bg-gradient-to-br ${getThumbnailGradient(item.source_platform)} ${isYouTube ? "aspect-video" : "h-40"}`}
        >
          <PlatformIcon platform={item.source_platform} url={item.url} faviconUrl={item.favicon_url} className="h-12 w-12 opacity-60" />
        </div>
      )}

      {/* Title + metadata */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <PlatformIcon platform={item.source_platform} url={item.url} faviconUrl={item.favicon_url} className="h-4 w-4" />
          <span className="text-xs uppercase tracking-wider text-gray-500 dark:text-gray-400 font-medium">
            {item.source_platform === "generic" ? "Web" : item.source_platform}
          </span>
          <span className="text-gray-300 dark:text-gray-700">·</span>
          <span className="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500">
            <Clock className="h-3 w-3" />
            {formatDate(item.created_at)}
          </span>
        </div>
        <h1 className="text-xl md:text-2xl font-bold text-gray-900 dark:text-gray-100 leading-tight">
          {item.title || item.url || "Untitled"}
        </h1>
        {item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-[#0096C7] hover:text-[#0077A8] mt-2 truncate max-w-full cursor-pointer transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5 flex-shrink-0" />
            <span className="truncate">{item.url}</span>
          </a>
        )}
      </div>

      {item.summary && (
        <div className="rounded-2xl border border-[#0096C7]/20 dark:border-sky-800/50 bg-gradient-to-br from-sky-50 to-white dark:from-sky-950/30 dark:to-gray-900 p-5">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[#0096C7] mb-2 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#0096C7]" />
            AI Summary
          </h2>
          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
            {item.summary}
          </p>
        </div>
      )}

      {tags.length > 0 && (
        <div className="mb-6">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-3">
            Tags
          </h2>
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => (
              <Link
                key={tag.tag_id}
                to={`/tags/${tag.tag_id}`}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs hover:opacity-80 transition-opacity cursor-pointer"
                style={{
                  backgroundColor: tag.tag_color ? `${tag.tag_color}20` : undefined,
                  color: tag.tag_color || undefined,
                }}
              >
                {!tag.tag_color && (
                  <span className="px-2.5 py-1 bg-sky-50 dark:bg-sky-900/20 text-sky-600 rounded-full text-xs">
                    {tag.tag_name}
                  </span>
                )}
                {tag.tag_color && tag.tag_name}
                {tag.ai_generated && tag.confidence > 0 && (
                  <span className="text-[10px] opacity-60">
                    {Math.round(tag.confidence * 100)}%
                  </span>
                )}
              </Link>
            ))}
          </div>
        </div>
      )}

      {hasDisplayableMetadata && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5 mb-6">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-3">
            Details
          </h2>
          <PlatformMetadata platform={item.source_platform} metadata={metadata} />
        </div>
      )}

      {item.content && (
        <TextHighlighter itemId={item.id} highlights={highlights}>
          <ContentRenderer
            content={item.content}
            rawContent={item.raw_content}
            sourceUrl={item.url}
            sourcePlatform={item.source_platform}
          />
        </TextHighlighter>
      )}

      {/* Reading list action */}
      <div className="flex items-center gap-3">
        {item.reading_status === "reading_list" ? (
          <button
            onClick={() => markAsRead.mutate({ id: item.id, type: "item" })}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-medium transition-colors"
          >
            <Check className="w-4 h-4" />
            Mark as Read
          </button>
        ) : item.reading_status === "read" ? (
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400">
            <Check className="w-3.5 h-3.5" />
            Read
          </span>
        ) : null}
        <button
          onClick={() => toggleReadingList.mutate({ id: item.id, type: "item", add: item.reading_status !== "reading_list" })}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            item.reading_status === "reading_list"
              ? "bg-sky-50 dark:bg-sky-900/20 text-sky-600 dark:text-sky-400 border border-sky-200 dark:border-sky-800"
              : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-sky-50 dark:hover:bg-sky-900/20 hover:text-sky-600"
          }`}
        >
          <BookMarked className="w-4 h-4" />
          {item.reading_status === "reading_list" ? "In Reading List" : "Add to Reading List"}
        </button>
      </div>

      {/* Multi-link section */}
      <ItemLinksSection itemId={item.id} />

      <div className="mt-8 border-t border-gray-200 dark:border-gray-800 pt-6">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-3">
          Related Items
        </h2>
        {relatedItems && relatedItems.length > 0 ? (
          <div className="flex gap-3 overflow-x-auto pb-2 sm:grid sm:grid-cols-2 md:grid-cols-3 sm:overflow-visible">
            {relatedItems.map((related) => (
              <Link
                key={related.id}
                to={`/item/${related.id}`}
                className="flex-shrink-0 w-48 sm:w-auto flex flex-col gap-1 p-3 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 hover:border-sky-200 dark:hover:border-sky-800 hover:shadow-md transition-all duration-200 cursor-pointer"
              >
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-sky-600">
                    <PlatformIcon platform={related.source_platform} url={related.url} className="h-4 w-4" />
                  </span>
                  <span className="text-[10px] uppercase tracking-wider text-gray-400 font-medium truncate">
                    {related.source_platform}
                  </span>
                </div>
                <p className="text-sm font-medium text-gray-800 dark:text-gray-200 line-clamp-2 leading-snug">
                  {related.title || "Untitled"}
                </p>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400 dark:text-gray-500 italic">
            No related items found.
          </p>
        )}
      </div>

      <div className="mt-8 border-t border-gray-200 dark:border-gray-800 pt-6">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-4">
          Comments
        </h2>
        <div className="flex gap-2 mb-5 w-full">
          <input
            ref={commentInputRef}
            type="text"
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddComment()}
            placeholder="Add a comment..."
            className="flex-1 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm focus:ring-2 focus:ring-sky-500 focus:outline-none"
          />
          <button
            onClick={handleAddComment}
            disabled={!commentText.trim() || addComment.isPending}
            aria-label="Post comment"
            className="p-2.5 rounded-lg bg-sky-600 text-white hover:bg-sky-700 disabled:opacity-50 transition-all duration-200 cursor-pointer flex-shrink-0"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        {comments && comments.length > 0 ? (
          <div className="space-y-3 w-full">
            {comments.map((comment) => {
              const initial = comment.user_display_name?.charAt(0)?.toUpperCase() ?? "?";
              return (
                <div
                  key={comment.id}
                  className="p-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900"
                >
                  <div className="flex items-center gap-2.5 mb-2">
                    <div
                      className="flex-shrink-0 w-7 h-7 rounded-full bg-sky-100 dark:bg-sky-900/40 text-sky-700 dark:text-sky-300 flex items-center justify-center text-xs font-semibold select-none"
                      aria-hidden="true"
                    >
                      {initial}
                    </div>
                    <span className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                      {comment.user_display_name}
                    </span>
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {formatDate(comment.created_at)}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed pl-9">
                    {comment.content}
                  </p>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-gray-400 dark:text-gray-500 italic">
            No comments on this item.
          </p>
        )}
      </div>

      {shareOpen && (
        <ShareDialog
          itemId={id}
          onClose={() => setShareOpen(false)}
        />
      )}

      {editOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setEditOpen(false)}
          />
          <div className="relative z-10">
            <EditBookmarkForm
              item={item}
              onClose={() => setEditOpen(false)}
              onUpdated={() => qc.invalidateQueries({ queryKey: ["items", id] })}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function ItemLinksSection({ itemId }: { itemId: string }) {
  const { data: links } = useItemLinks(itemId);
  const addLink = useAddItemLink();
  const removeLink = useRemoveItemLink();
  const [showAdd, setShowAdd] = useState(false);
  const [newUrl, setNewUrl] = useState("");
  const [newTitle, setNewTitle] = useState("");

  const handleAdd = () => {
    if (!newUrl.trim()) return;
    addLink.mutate({ itemId, url: newUrl.trim(), title: newTitle.trim() || undefined });
    setNewUrl("");
    setNewTitle("");
    setShowAdd(false);
  };

  if (!links?.length && !showAdd) {
    return (
      <div className="mt-4">
        <button
          onClick={() => setShowAdd(true)}
          className="inline-flex items-center gap-1.5 text-xs text-gray-400 hover:text-sky-500 transition-colors"
        >
          <LinkIcon className="w-3.5 h-3.5" />
          Add related links
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5 mb-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400">
          Related Links
        </h2>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-sky-500 transition-colors"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      {showAdd && (
        <div className="flex gap-2 mb-3">
          <input
            type="url"
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
            placeholder="https://..."
            className="flex-1 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-1.5"
            autoFocus
          />
          <input
            type="text"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="Title (optional)"
            className="w-40 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-1.5"
          />
          <button onClick={handleAdd} className="p-1.5 rounded-lg bg-sky-600 text-white hover:bg-sky-700">
            <Check className="w-4 h-4" />
          </button>
          <button onClick={() => setShowAdd(false)} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      <div className="space-y-2">
        {links?.map((link) => (
          <div
            key={link.id}
            className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 group"
          >
            <img
              src={`https://www.google.com/s2/favicons?domain=${link.domain}&sz=32`}
              alt=""
              className="w-4 h-4 rounded"
            />
            <div className="flex-1 min-w-0">
              <a
                href={link.url.match(/^https?:\/\//i) ? link.url : '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-gray-800 dark:text-gray-200 hover:text-sky-600 truncate block"
              >
                {link.title || link.url}
              </a>
              <span className="text-[10px] text-gray-400">{link.domain}</span>
            </div>
            <button
              onClick={() => removeLink.mutate({ itemId, linkId: link.id })}
              className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-500 transition-all"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
