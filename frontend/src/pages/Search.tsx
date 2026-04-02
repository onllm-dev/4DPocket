import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Search as SearchIcon, Loader2 } from "lucide-react";
import { useSearch } from "@/hooks/use-items";
import { BookmarkCard } from "@/components/bookmark/BookmarkCard";

export default function Search() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get("q") ?? "";
  const [input, setInput] = useState(initialQuery);
  const [query, setQuery] = useState(initialQuery);

  const { data: results, isLoading, isFetching } = useSearch(query);

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

      <div className="relative mb-8">
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
