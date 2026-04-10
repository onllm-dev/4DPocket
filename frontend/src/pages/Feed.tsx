import { useState } from "react";
import {
  Rss,
  ExternalLink,
  Plus,
  Trash2,
  Check,
  X,
  Clock,
  ListFilter,
  ChevronLeft,
  Loader2,
  Globe,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import { timeAgo } from "@/lib/utils";
import {
  useFeeds,
  useCreateFeed,
  useDeleteFeed,
  useFeedEntries,
  useApproveFeedEntry,
  useRejectFeedEntry,
  type Feed as FeedType,
} from "@/hooks/use-rss";
import { useCollections } from "@/hooks/use-collections";

interface KnowledgeFeedItem {
  id: string;
  title: string;
  url: string | null;
  source_platform: string;
  summary: string | null;
  created_at: string;
  owner_display_name: string;
}

type Tab = "knowledge" | "manage";

const FORMAT_OPTIONS = [
  { value: "rss", label: "RSS" },
  { value: "atom", label: "Atom" },
  { value: "json", label: "JSON Feed" },
];

const FORMAT_COLORS: Record<string, string> = {
  rss: "bg-orange-100 dark:bg-orange-900/20 text-orange-700 dark:text-orange-400",
  atom: "bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400",
  json: "bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400",
};

export default function Feed() {
  const [tab, setTab] = useState<Tab>("knowledge");
  const [reviewingFeedId, setReviewingFeedId] = useState<string | null>(null);

  return (
    <div className="animate-fade-in max-w-4xl mx-auto px-4">
      <div className="flex items-center gap-3 mb-6">
        <Rss className="w-6 h-6 text-sky-600" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Feeds</h1>
      </div>

      {/* Tab toggle */}
      <div className="flex items-center gap-2 mb-6">
        <button
          onClick={() => { setTab("knowledge"); setReviewingFeedId(null); }}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer ${
            tab === "knowledge"
              ? "bg-sky-600 text-white"
              : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-sm"
          }`}
        >
          Knowledge Feed
        </button>
        <button
          onClick={() => { setTab("manage"); setReviewingFeedId(null); }}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer ${
            tab === "manage"
              ? "bg-sky-600 text-white"
              : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-sm"
          }`}
        >
          Manage Feeds
        </button>
      </div>

      {tab === "knowledge" ? (
        <KnowledgeFeedTab />
      ) : reviewingFeedId ? (
        <ApprovalQueue feedId={reviewingFeedId} onBack={() => setReviewingFeedId(null)} />
      ) : (
        <ManageFeedsTab onReview={setReviewingFeedId} />
      )}
    </div>
  );
}

/* ---------- Knowledge Feed Tab ---------- */

function KnowledgeFeedTab() {
  const { data: items, isLoading } = useQuery<KnowledgeFeedItem[]>({
    queryKey: ["knowledge-feed"],
    queryFn: () => api.get("/api/v1/feeds"),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 space-y-2">
            <div className="h-5 w-3/4 animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
            <div className="h-3 w-full animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
            <div className="flex gap-2 mt-2">
              <div className="h-3 w-20 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
              <div className="h-3 w-16 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!items?.length) {
    return (
      <div className="text-center py-16 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
        <Rss className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
        <p className="text-gray-700 dark:text-gray-300 text-lg font-medium mb-1">No feed items</p>
        <p className="text-sm text-gray-400 dark:text-gray-500">Follow other users or add RSS feeds to populate this page.</p>
      </div>
    );
  }

  return (
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
                <span>&middot;</span>
                <span>{item.source_platform}</span>
                <span>&middot;</span>
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
  );
}

/* ---------- Manage Feeds Tab ---------- */

function ManageFeedsTab({ onReview }: { onReview: (feedId: string) => void }) {
  const { data: feeds, isLoading } = useFeeds();
  const [showAddForm, setShowAddForm] = useState(false);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">RSS / Atom / JSON Feeds</h2>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-sky-600 text-white hover:bg-sky-700 transition-colors cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          Add Feed
        </button>
      </div>

      {showAddForm && <AddFeedForm onClose={() => setShowAddForm(false)} />}

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 space-y-2">
              <div className="h-5 w-1/2 animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
              <div className="h-3 w-full animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
            </div>
          ))}
        </div>
      ) : !feeds?.length ? (
        <div className="text-center py-12 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <Rss className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400 text-sm">No feeds configured</p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Add an RSS, Atom, or JSON feed URL above.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {feeds.map((feed) => (
            <FeedCard key={feed.id} feed={feed} onReview={onReview} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- Feed Card ---------- */

function FeedCard({ feed, onReview }: { feed: FeedType; onReview: (feedId: string) => void }) {
  const deleteFeed = useDeleteFeed();

  const handleDelete = () => {
    if (window.confirm("Delete this feed? This cannot be undone.")) {
      deleteFeed.mutate(feed.id);
    }
  };

  const formatBadgeClass = FORMAT_COLORS[feed.format] ?? "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400";

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Globe className="w-4 h-4 text-sky-500 shrink-0" />
            <h3 className="font-medium text-gray-900 dark:text-gray-100 truncate">
              {feed.title || feed.url}
            </h3>
          </div>
          <p className="text-xs text-gray-400 dark:text-gray-500 truncate mb-2">{feed.url}</p>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${formatBadgeClass}`}>
              {feed.format.toUpperCase()}
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
              feed.mode === "auto"
                ? "bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400"
                : "bg-amber-100 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400"
            }`}>
              {feed.mode === "auto" ? "Auto" : "Approval"}
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
              feed.is_active
                ? "bg-emerald-100 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400"
                : "bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-400"
            }`}>
              {feed.is_active ? "Active" : "Inactive"}
            </span>
            {feed.last_fetched_at && (
              <span className="flex items-center gap-1 text-[10px] text-gray-400 dark:text-gray-500">
                <Clock className="w-3 h-3" />
                {timeAgo(feed.last_fetched_at)}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {feed.mode === "approval" && (
            <button
              onClick={() => onReview(feed.id)}
              className="p-2 rounded-lg text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-900/20 transition-colors cursor-pointer"
              title="Review pending entries"
            >
              <ListFilter className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={handleDelete}
            disabled={deleteFeed.isPending}
            className="p-2 rounded-lg text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors cursor-pointer disabled:opacity-50"
            title="Delete feed"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------- Add Feed Form ---------- */

function AddFeedForm({ onClose }: { onClose: () => void }) {
  const createFeed = useCreateFeed();
  const { data: collections } = useCollections();

  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [format, setFormat] = useState("rss");
  const [mode, setMode] = useState("auto");
  const [filters, setFilters] = useState("");
  const [collectionId, setCollectionId] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    createFeed.mutate(
      {
        url: url.trim(),
        title: title.trim() || undefined,
        format,
        mode,
        filters: filters.trim() || undefined,
        target_collection_id: collectionId || undefined,
      },
      { onSuccess: onClose }
    );
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-sky-200 dark:border-sky-800 bg-sky-50/50 dark:bg-sky-900/10 p-4 space-y-3"
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="sm:col-span-2">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            Feed URL *
          </label>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/feed.xml"
            required
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-600"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            Title
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="My Feed"
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-600"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            Format
          </label>
          <select
            value={format}
            onChange={(e) => setFormat(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-600"
          >
            {FORMAT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            Mode
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setMode("auto")}
              className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                mode === "auto"
                  ? "bg-sky-600 text-white"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
              }`}
            >
              Auto
            </button>
            <button
              type="button"
              onClick={() => setMode("approval")}
              className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                mode === "approval"
                  ? "bg-sky-600 text-white"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
              }`}
            >
              Approval
            </button>
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            Collection
          </label>
          <select
            value={collectionId}
            onChange={(e) => setCollectionId(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-600"
          >
            <option value="">None</option>
            {collections?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="sm:col-span-2">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            Keyword Filter
          </label>
          <input
            type="text"
            value={filters}
            onChange={(e) => setFilters(e.target.value)}
            placeholder="e.g. react, typescript, ai"
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-600"
          />
        </div>
      </div>
      <div className="flex items-center justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-1.5 rounded-lg text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={createFeed.isPending || !url.trim()}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium bg-sky-600 text-white hover:bg-sky-700 transition-colors cursor-pointer disabled:opacity-50"
        >
          {createFeed.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          Add Feed
        </button>
      </div>
    </form>
  );
}

/* ---------- Approval Queue ---------- */

function ApprovalQueue({ feedId, onBack }: { feedId: string; onBack: () => void }) {
  const { data: entries, isLoading } = useFeedEntries(feedId);
  const approveMut = useApproveFeedEntry();
  const rejectMut = useRejectFeedEntry();

  const pending = entries?.filter((e) => e.status === "pending") ?? [];

  return (
    <div className="space-y-4">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors cursor-pointer"
      >
        <ChevronLeft className="w-4 h-4" />
        Back to feeds
      </button>

      <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
        Pending Entries ({pending.length})
      </h2>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 space-y-2">
              <div className="h-4 w-2/3 animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
              <div className="h-3 w-full animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
            </div>
          ))}
        </div>
      ) : pending.length === 0 ? (
        <div className="text-center py-12 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <Check className="w-10 h-10 text-green-400 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400 text-sm">No pending entries to review</p>
        </div>
      ) : (
        <div className="space-y-3">
          {pending.map((entry) => (
            <div
              key={entry.id}
              className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <h3 className="font-medium text-gray-900 dark:text-gray-100 truncate">
                    {entry.title || "Untitled"}
                  </h3>
                  {entry.content_snippet && (
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">
                      {entry.content_snippet}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-2">
                    {entry.url && (
                      <a
                        href={entry.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-sky-600 hover:underline truncate max-w-xs"
                      >
                        {entry.url}
                      </a>
                    )}
                    <span className="text-[10px] text-gray-400">{timeAgo(entry.created_at)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => approveMut.mutate({ feedId, entryId: entry.id })}
                    disabled={approveMut.isPending}
                    className="p-2 rounded-lg text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors cursor-pointer disabled:opacity-50"
                    title="Approve"
                  >
                    <Check className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => rejectMut.mutate({ feedId, entryId: entry.id })}
                    disabled={rejectMut.isPending}
                    className="p-2 rounded-lg text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors cursor-pointer disabled:opacity-50"
                    title="Reject"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
