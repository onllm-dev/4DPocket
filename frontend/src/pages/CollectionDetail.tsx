import { Link, useParams } from "react-router-dom";
import { ArrowLeft, FolderOpen, Grid3x3, List } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useUIStore } from "@/stores/ui-store";
import { BookmarkCard } from "@/components/bookmark/BookmarkCard";

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

  const {
    data: collection,
    isLoading: collectionLoading,
  } = useQuery<Collection>({
    queryKey: ["collection", id],
    queryFn: () => api.get(`/api/v1/collections/${id}`),
    enabled: !!id,
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
  }>>({
    queryKey: ["collection", id, "items"],
    queryFn: () => api.get(`/api/v1/collections/${id}/items`),
    enabled: !!id,
  });

  const isLoading = collectionLoading || itemsLoading;

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
