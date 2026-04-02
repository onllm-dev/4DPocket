import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Search as SearchIcon, Loader2, Sparkles, AlignLeft } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { BookmarkCard } from "@/components/bookmark/BookmarkCard";

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
}

interface SearchFilters {
  platforms: string[];
  item_types: string[];
}

export default function Search() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get("q") ?? "";
  const [input, setInput] = useState(initialQuery);
  const [query, setQuery] = useState(initialQuery);
  const [semantic, setSemantic] = useState(false);
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<string | null>(null);

  const { data: filters } = useQuery<SearchFilters>({
    queryKey: ["search-filters"],
    queryFn: () => api.get("/api/v1/search/filters"),
  });

  // Build semantic search URL with optional filters
  const semanticUrl = query.length >= 2
    ? `/api/v1/search/semantic?q=${encodeURIComponent(query)}${selectedPlatform ? `&source_platform=${selectedPlatform}` : ""}${selectedType ? `&item_type=${selectedType}` : ""}`
    : null;

  const { data: semanticResults, isLoading: semanticLoading, isFetching: semanticFetching } =
    useQuery<Item[]>({
      queryKey: ["search-semantic", query, selectedPlatform, selectedType],
      queryFn: () => api.get(semanticUrl!),
      enabled: semantic && query.length >= 2,
    });

  // Full-text search (existing hook) — but we need filter support too
  const fulltextUrl = query.length >= 2
    ? `/api/v1/search?q=${encodeURIComponent(query)}${selectedPlatform ? `&source_platform=${selectedPlatform}` : ""}${selectedType ? `&item_type=${selectedType}` : ""}`
    : "";

  const { data: fulltextResults, isLoading: fulltextLoading, isFetching: fulltextFetching } =
    useQuery<Item[]>({
      queryKey: ["search", query, selectedPlatform, selectedType],
      queryFn: () => api.get(fulltextUrl),
      enabled: !semantic && query.length >= 2,
    });

  const results = semantic ? semanticResults : fulltextResults;
  const isLoading = semantic ? semanticLoading : fulltextLoading;
  const isFetching = semantic ? semanticFetching : fulltextFetching;

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

  const items = results ?? [];
  const showSkeleton = (isLoading || isFetching) && query.length >= 2;

  return (
    <div className="animate-fade-in p-6 max-w-4xl mx-auto">
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
          placeholder="Search your knowledge base..."
          autoFocus
          className="w-full pl-12 pr-12 py-3.5 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-600 transition-all duration-200 shadow-sm"
        />
        {showSkeleton && (
          <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 animate-spin" />
        )}
      </div>

      {/* Search mode toggle */}
      <div className="flex items-center gap-2 mb-4">
        <button
          onClick={() => setSemantic(false)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 cursor-pointer ${
            !semantic
              ? "bg-sky-600 text-white"
              : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-sm"
          }`}
        >
          <AlignLeft className="h-3.5 w-3.5" />
          Full-text
        </button>
        <button
          onClick={() => setSemantic(true)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 cursor-pointer ${
            semantic
              ? "bg-sky-600 text-white"
              : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-sm"
          }`}
        >
          <Sparkles className="h-3.5 w-3.5" />
          Semantic
        </button>
      </div>

      {/* Filter chips */}
      {(filters?.platforms?.length || filters?.item_types?.length) ? (
        <div className="flex flex-wrap gap-2 mb-6">
          {filters.platforms?.map((platform) => (
            <button
              key={platform}
              onClick={() =>
                setSelectedPlatform(selectedPlatform === platform ? null : platform)
              }
              className={`px-3 py-1 rounded-full text-xs font-medium transition-all duration-200 cursor-pointer ${
                selectedPlatform === platform
                  ? "bg-sky-600 text-white"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-sm"
              }`}
            >
              {platform}
            </button>
          ))}
          {filters.item_types?.map((type) => (
            <button
              key={type}
              onClick={() =>
                setSelectedType(selectedType === type ? null : type)
              }
              className={`px-3 py-1 rounded-full text-xs font-medium transition-all duration-200 cursor-pointer ${
                selectedType === type
                  ? "bg-violet-600 text-white"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-sm"
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      ) : null}

      {!query || query.length < 2 ? (
        <div className="text-center py-16">
          <SearchIcon className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 text-lg mb-1">
            Search your knowledge base
          </p>
          <p className="text-sm text-gray-400 dark:text-gray-500">
            Type at least 2 characters to search
          </p>
        </div>
      ) : showSkeleton && items.length === 0 ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg"
            />
          ))}
        </div>
      ) : items.length === 0 && !isLoading ? (
        <div className="text-center py-16">
          <SearchIcon className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 text-lg mb-1">
            No results for &ldquo;{query}&rdquo;
          </p>
          <p className="text-sm text-gray-400 dark:text-gray-500">
            Try different keywords
          </p>
        </div>
      ) : (
        <div>
          {items.length > 0 && (
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              {items.length} result{items.length !== 1 ? "s" : ""} for &ldquo;
              {query}&rdquo;
            </p>
          )}
          <div className="flex flex-col gap-3">
            {items.map((item) => (
              <BookmarkCard key={item.id} item={item} variant="list" />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
