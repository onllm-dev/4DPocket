import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Search as SearchIcon, Loader2, Sparkles, AlignLeft, StickyNote, Zap, Tag, Calendar, Star, Archive } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import DOMPurify from "dompurify";
import { api } from "@/api/client";
import { BookmarkCard } from "@/components/bookmark/BookmarkCard";
import NoteCard from "@/components/bookmark/NoteCard";

interface Item {
  id: string;
  item_type: string;
  source_platform: string;
  url: string | null;
  title: string | null;
  description: string | null;
  content: string | null;
  summary: string | null;
  media: Array<{ type: string; url: string; role: string }>;
  item_metadata: Record<string, unknown>;
  is_favorite: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  title_snippet?: string | null;
  content_snippet?: string | null;
  sources?: string[];
}

interface SearchFilters {
  platforms: Array<{ name: string; count: number }>;
  types: string[];
  tags: Array<{ name: string; slug: string; count: number }>;
}

interface UnifiedResult {
  items: Item[];
  notes: Array<{ id: string; title: string | null; content: string; created_at: string; updated_at: string }>;
  total: number;
}

const PLATFORM_LABELS: Record<string, string> = {
  generic: "Web",
  youtube: "YouTube",
  github: "GitHub",
  reddit: "Reddit",
  twitter: "Twitter",
  hackernews: "Hacker News",
  stackoverflow: "Stack Overflow",
  wikipedia: "Wikipedia",
  arxiv: "arXiv",
  medium: "Medium",
  substack: "Substack",
  mastodon: "Mastodon",
  bluesky: "Bluesky",
  instagram: "Instagram",
  tiktok: "TikTok",
  spotify: "Spotify",
  goodreads: "Goodreads",
};

const TYPE_LABELS: Record<string, string> = {
  url: "Link",
  note: "Note",
  image: "Image",
  video: "Video",
  audio: "Audio",
  document: "Document",
  pdf: "PDF",
  article: "Article",
  file: "File",
};

type SearchMode = "fulltext" | "semantic" | "hybrid";

function formatPlatformLabel(raw: string | undefined | null): string {
  if (!raw) return "";
  const cleaned = raw.replace(/^SourcePlatform\./, "");
  return PLATFORM_LABELS[cleaned] ?? cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

function formatTypeLabel(raw: string | undefined | null): string {
  if (!raw) return "";
  return TYPE_LABELS[raw] ?? raw.charAt(0).toUpperCase() + raw.slice(1);
}

export default function Search() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get("q") ?? "";
  const [input, setInput] = useState(initialQuery);
  const [query, setQuery] = useState(initialQuery);
  const [mode, setMode] = useState<SearchMode>("fulltext");
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [showFavorites, setShowFavorites] = useState(false);
  const [showArchived, setShowArchived] = useState(false);

  const { data: filters } = useQuery<SearchFilters>({
    queryKey: ["search-filters"],
    queryFn: () => api.get("/api/v1/search/filters"),
  });

  // Build filter params
  const filterParams = new URLSearchParams();
  if (selectedPlatform) filterParams.set("source_platform", selectedPlatform);
  if (selectedType) filterParams.set("item_type", selectedType);
  if (selectedTag) filterParams.set("tag", selectedTag);
  if (showFavorites) filterParams.set("is_favorite", "true");
  if (showArchived) filterParams.set("is_archived", "true");
  const filterStr = filterParams.toString() ? `&${filterParams.toString()}` : "";

  // Unified search (items + notes) — default mode
  const unifiedUrl = query.length >= 2
    ? `/api/v1/search/unified?q=${encodeURIComponent(query)}${filterStr}`
    : null;

  const { data: unifiedResults, isLoading: unifiedLoading, isFetching: unifiedFetching } =
    useQuery<UnifiedResult>({
      queryKey: ["search-unified", query, selectedPlatform, selectedType, selectedTag, showFavorites, showArchived],
      queryFn: () => api.get(unifiedUrl!),
      enabled: mode === "fulltext" && query.length >= 2,
    });

  // Semantic search
  const semanticUrl = query.length >= 2
    ? `/api/v1/search/semantic?q=${encodeURIComponent(query)}${filterStr}`
    : null;

  const { data: semanticResults, isLoading: semanticLoading, isFetching: semanticFetching } =
    useQuery<Item[]>({
      queryKey: ["search-semantic", query, selectedPlatform, selectedType],
      queryFn: () => api.get(semanticUrl!),
      enabled: mode === "semantic" && query.length >= 2,
    });

  // Hybrid search
  const hybridUrl = query.length >= 2
    ? `/api/v1/search/hybrid?q=${encodeURIComponent(query)}${filterStr}`
    : null;

  const { data: hybridResults, isLoading: hybridLoading, isFetching: hybridFetching } =
    useQuery<Item[]>({
      queryKey: ["search-hybrid", query, selectedPlatform, selectedType],
      queryFn: () => api.get(hybridUrl!),
      enabled: mode === "hybrid" && query.length >= 2,
    });

  const items = mode === "fulltext"
    ? (unifiedResults?.items ?? [])
    : mode === "semantic"
    ? (semanticResults ?? [])
    : (hybridResults ?? []);

  const notes = mode === "fulltext" ? (unifiedResults?.notes ?? []) : [];
  const isLoading = mode === "fulltext" ? unifiedLoading : mode === "semantic" ? semanticLoading : hybridLoading;
  const isFetching = mode === "fulltext" ? unifiedFetching : mode === "semantic" ? semanticFetching : hybridFetching;
  const totalResults = items.length + notes.length;
  const showSkeleton = (isLoading || isFetching) && query.length >= 2;

  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(input);
      if (input) {
        setSearchParams({ q: input });
      } else {
        setSearchParams({});
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [input, setSearchParams]);

  const modes: { key: SearchMode; label: string; icon: typeof AlignLeft; desc: string }[] = [
    { key: "fulltext", label: "Full-text", icon: AlignLeft, desc: "Keyword search with fuzzy fallback" },
    { key: "hybrid", label: "Hybrid", icon: Zap, desc: "Keyword + AI semantic combined" },
    { key: "semantic", label: "Semantic", icon: Sparkles, desc: "AI meaning-based search" },
  ];

  return (
    <div className="animate-fade-in p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <SearchIcon className="h-6 w-6 text-sky-600" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Search
        </h1>
      </div>

      <div className="relative mb-4">
        <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
        <input
          type="search"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Search your knowledge base... (try tag:ml is:favorite after:2024-01)"
          autoFocus
          className="w-full pl-12 pr-12 py-3.5 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-600 transition-all duration-200 shadow-sm"
        />
        {showSkeleton && (
          <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 animate-spin" />
        )}
      </div>

      {/* Search mode toggle */}
      <div className="flex items-center gap-2 mb-4">
        {modes.map(({ key, label, icon: Icon, desc }) => (
          <button
            key={key}
            onClick={() => setMode(key)}
            title={desc}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 cursor-pointer ${
              mode === key
                ? "bg-sky-600 text-white"
                : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-sm"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Quick filter toggles */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <button
          onClick={() => setShowFavorites(!showFavorites)}
          className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-all cursor-pointer ${
            showFavorites
              ? "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 ring-1 ring-amber-300 dark:ring-amber-700"
              : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"
          }`}
        >
          <Star className="h-3 w-3" />
          Favorites
        </button>
        <button
          onClick={() => setShowArchived(!showArchived)}
          className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-all cursor-pointer ${
            showArchived
              ? "bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 ring-1 ring-slate-400"
              : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"
          }`}
        >
          <Archive className="h-3 w-3" />
          Archived
        </button>
      </div>

      {/* Platform + Type + Tag filter chips */}
      {(filters?.platforms?.length || filters?.types?.length || filters?.tags?.length) ? (
        <div className="flex flex-wrap gap-2 mb-6">
          {filters?.platforms?.map((p) => (
            <button
              key={p.name}
              onClick={() => setSelectedPlatform(selectedPlatform === p.name ? null : p.name)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-all duration-200 cursor-pointer ${
                selectedPlatform === p.name
                  ? "bg-sky-600 text-white"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-sm"
              }`}
            >
              {formatPlatformLabel(p.name)} ({p.count})
            </button>
          ))}
          {filters?.types?.map((type) => (
            <button
              key={type}
              onClick={() => setSelectedType(selectedType === type ? null : type)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-all duration-200 cursor-pointer ${
                selectedType === type
                  ? "bg-violet-600 text-white"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-sm"
              }`}
            >
              {formatTypeLabel(type)}
            </button>
          ))}
          {filters?.tags?.slice(0, 15).map((t) => (
            <button
              key={t.slug}
              onClick={() => setSelectedTag(selectedTag === t.slug ? null : t.slug)}
              className={`flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium transition-all duration-200 cursor-pointer ${
                selectedTag === t.slug
                  ? "bg-emerald-600 text-white"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-sm"
              }`}
            >
              <Tag className="h-3 w-3" />
              {t.name} ({t.count})
            </button>
          ))}
        </div>
      ) : null}

      {!query || query.length < 2 ? (
        <div className="text-center py-16 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <SearchIcon className="h-12 w-12 text-[#0096C7]/20 dark:text-sky-900 mx-auto mb-4" />
          <p className="text-gray-700 dark:text-gray-300 text-lg font-medium mb-1">
            Search your knowledge base
          </p>
          <p className="text-sm text-gray-400 dark:text-gray-500 max-w-md mx-auto">
            Type at least 2 characters. Try URLs, keywords, or filters like{" "}
            <code className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-xs">tag:ml</code>{" "}
            <code className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-xs">is:favorite</code>{" "}
            <code className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-xs">after:2024-01</code>
          </p>
        </div>
      ) : showSkeleton && totalResults === 0 ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 p-4 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
              <div className="w-16 h-16 rounded-xl animate-pulse bg-gray-100 dark:bg-gray-800 flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3 w-24 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
                <div className="h-4 w-3/4 animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-3 w-1/2 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : totalResults === 0 && !isLoading ? (
        <div className="text-center py-16 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <SearchIcon className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-700 dark:text-gray-300 text-lg font-medium mb-1">
            No results for &ldquo;{query}&rdquo;
          </p>
          <p className="text-sm text-gray-400 dark:text-gray-500">
            {mode === "fulltext"
              ? "Try different keywords, a URL, or switch to Hybrid/Semantic search"
              : "Try different keywords or switch to Full-text search"}
          </p>
        </div>
      ) : (
        <div>
          {totalResults > 0 && (
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              {totalResults} result{totalResults !== 1 ? "s" : ""} for &ldquo;{query}&rdquo;
              {mode === "hybrid" && <span className="ml-1 text-xs text-sky-500">(keyword + semantic fusion)</span>}
            </p>
          )}

          {/* Note results */}
          {notes.length > 0 && (
            <div className="mb-6">
              <div className="flex items-center gap-2 mb-3">
                <StickyNote className="h-4 w-4 text-amber-500" />
                <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                  Notes ({notes.length})
                </h2>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {notes.map((note) => (
                  <NoteCard key={note.id} note={note} />
                ))}
              </div>
            </div>
          )}

          {/* Item results */}
          {items.length > 0 && (
            <div className="flex flex-col gap-3">
              {items.map((item) => (
                <div key={item.id}>
                  <BookmarkCard item={item} variant="list" />
                  {item.content_snippet && (
                    <p
                      className="mt-1 ml-2 text-xs text-gray-500 dark:text-gray-400 line-clamp-2 [&_mark]:bg-yellow-200 [&_mark]:dark:bg-yellow-800 [&_mark]:rounded-sm [&_mark]:px-0.5"
                      dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(item.content_snippet, { ALLOWED_TAGS: ["mark"] }) }}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
