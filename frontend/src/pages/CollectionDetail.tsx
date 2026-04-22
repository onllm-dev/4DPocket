import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, FolderOpen, Grid3x3, List, Plus, Search, X, AlertCircle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useUIStore } from "@/stores/ui-store";
import { BookmarkCard } from "@/components/bookmark/BookmarkCard";
import { useSearch } from "@/hooks/use-items";
import { useAddItemToCollection } from "@/hooks/use-collections";

interface Collection {
  id: string;
  name: string;
  description: string | null;
  icon: string | null;
  is_public: boolean;
}

export default function CollectionDetail() {
  const { id } = useParams<{ id: string }>();
  const { viewMode, setViewMode } = useUIStore();
  const [showAddItems, setShowAddItems] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const addItem = useAddItemToCollection();
  const { data: searchResults } = useSearch(searchQuery);

  const {
    data: collection,
    isLoading: collectionLoading,
    isError: collectionError,
  } = useQuery<Collection>({
    queryKey: ["collection", id],
    queryFn: () => api.get(`/api/v1/collections/${id}`),
    enabled: !!id,
    retry: false,
  });

  const {
    data: items,
    isLoading: itemsLoading,
  } = useQuery<Array<{
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
    item_metadata?: Record<string, unknown> | null;
  }>>({
    queryKey: ["collection", id, "items"],
    queryFn: () => api.get(`/api/v1/collections/${id}/items`),
    enabled: !!id,
  });

  const isLoading = collectionLoading || itemsLoading;

  if (collectionError) {
    return (
      <div className="animate-fade-in p-6 max-w-6xl mx-auto">
        <Link
          to="/collections"
          className="inline-flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 mb-6 p-2 -ml-2 rounded-xl hover:bg-sky-50 dark:hover:bg-gray-800 transition-all cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to collections
        </Link>
        <div className="text-center py-20 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <AlertCircle className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-900 dark:text-gray-100 text-lg font-medium mb-1">
            Collection not found
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
            This collection doesn&apos;t exist or you don&apos;t have access to it.
          </p>
          <Link
            to="/collections"
            className="inline-flex items-center gap-2 px-4 py-2 bg-sky-600 text-white rounded-lg text-sm font-medium hover:bg-sky-700 transition-colors cursor-pointer"
          >
            Go to collections
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link
            to="/collections"
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-all duration-200 cursor-pointer"
            aria-label="Back to collections"
          >
            <ArrowLeft className="h-5 w-5 text-gray-500" />
          </Link>
          <FolderOpen className="h-6 w-6 text-sky-600" />
          {collectionLoading ? (
            <div className="h-7 w-48 animate-pulse bg-gray-200 dark:bg-gray-800 rounded" />
          ) : (
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              {collection?.name ?? "Collection"}
            </h1>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowAddItems(!showAddItems)}
            className="p-2.5 rounded-lg text-sm bg-sky-600 text-white hover:bg-sky-700 transition-all duration-200 cursor-pointer mr-2"
            aria-label="Add items"
          >
            <Plus className="h-4 w-4" />
          </button>
          <button
            onClick={() => setViewMode("grid")}
            className={`p-2.5 rounded-lg text-sm transition-all duration-200 cursor-pointer ${
              viewMode === "grid"
                ? "bg-sky-600 text-white"
                : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-md"
            }`}
            aria-label="Grid view"
          >
            <Grid3x3 className="h-4 w-4" />
          </button>
          <button
            onClick={() => setViewMode("list")}
            className={`p-2.5 rounded-lg text-sm transition-all duration-200 cursor-pointer ${
              viewMode === "list"
                ? "bg-sky-600 text-white"
                : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-md"
            }`}
            aria-label="List view"
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      </div>

      {collection?.description && (
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
          {collection.description}
        </p>
      )}

      {showAddItems && (
        <div className="mb-6 p-4 border border-sky-200 dark:border-sky-800 rounded-xl bg-sky-50/50 dark:bg-sky-950/20">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Add Items to Collection</p>
            <button onClick={() => setShowAddItems(false)} className="p-1 text-gray-400 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search items to add..."
              className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
              autoFocus
            />
          </div>
          {searchResults && searchResults.length > 0 && (
            <div className="max-h-48 overflow-y-auto space-y-1">
              {searchResults.slice(0, 10).map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    addItem.mutate({ collectionId: id!, itemIds: [item.id] });
                  }}
                  className="w-full flex items-center gap-2 p-2 text-left text-sm rounded-lg hover:bg-white dark:hover:bg-gray-800 transition-colors"
                >
                  <Plus className="w-3.5 h-3.5 text-sky-500 shrink-0" />
                  <span className="truncate text-gray-800 dark:text-gray-200">
                    {item.title || item.url || "Untitled"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="h-48 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg"
            />
          ))}
        </div>
      ) : !items || items.length === 0 ? (
        <div className="text-center py-16 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm">
          <FolderOpen className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 text-lg mb-1">
            No items in this collection
          </p>
          <p className="text-gray-400 dark:text-gray-500 text-sm">
            Add items to this collection from the Knowledge Base
          </p>
        </div>
      ) : (
        <div
          className={
            viewMode === "grid"
              ? "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
              : "flex flex-col gap-3"
          }
        >
          {items.map((item) => (
            <BookmarkCard key={item.id} item={item} variant={viewMode} />
          ))}
        </div>
      )}
    </div>
  );
}
