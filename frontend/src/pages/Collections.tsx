import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FolderOpen, Plus, X } from "lucide-react";
import { useCollections, useCreateCollection } from "@/hooks/use-collections";

export default function Collections() {
  const navigate = useNavigate();
  const { data: collections, isLoading } = useCollections();
  const createCollection = useCreateCollection();

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    await createCollection.mutateAsync({
      name: name.trim(),
      description: description.trim() || undefined,
    });
    setName("");
    setDescription("");
    setShowForm(false);
  };

  return (
    <div className="animate-fade-in p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <FolderOpen className="h-6 w-6 text-sky-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Collections
          </h1>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-sky-600 text-white rounded-lg text-sm font-medium hover:shadow-md transition-all duration-200 cursor-pointer"
        >
          <Plus className="h-4 w-4" />
          New Collection
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5 mb-6 space-y-3"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100">
              Create Collection
            </h2>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 transition-all duration-200 cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Collection name..."
            autoFocus
            required
            className="w-full px-4 py-2.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-600"
          />
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description (optional)..."
            className="w-full px-4 py-2.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-600"
          />
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={createCollection.isPending}
              className="px-4 py-2 bg-sky-600 text-white rounded-lg text-sm font-medium hover:shadow-md transition-all duration-200 cursor-pointer disabled:opacity-50"
            >
              {createCollection.isPending ? "Creating..." : "Create"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded-lg text-sm cursor-pointer hover:shadow-md transition-all duration-200"
            >
              Cancel
            </button>
          </div>
          {createCollection.isError && <p className="text-sm text-red-500 mt-2">Failed to create collection. Please try again.</p>}
        </form>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 space-y-3">
              <div className="w-11 h-11 rounded-lg animate-pulse bg-gray-100 dark:bg-gray-800" />
              <div className="h-5 w-32 animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
              <div className="h-3 w-20 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
            </div>
          ))}
        </div>
      ) : !collections || collections.length === 0 ? (
        <div className="text-center py-16 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <FolderOpen className="h-12 w-12 text-[#0096C7]/20 dark:text-sky-900 mx-auto mb-4" />
          <p className="text-gray-700 dark:text-gray-300 text-lg font-medium mb-1">
            No collections yet
          </p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mb-6">
            Create a collection to organize your saved items
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-sky-600 text-white rounded-lg font-medium hover:shadow-md transition-all duration-200 cursor-pointer"
          >
            <Plus className="h-4 w-4" />
            Create your first collection
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {collections.map((col) => (
            <button
              key={col.id}
              onClick={() => navigate(`/collections/${col.id}`)}
              className="text-left rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5 hover:shadow-md transition-all duration-200 cursor-pointer"
            >
              <div className="p-2.5 rounded-lg bg-sky-50 dark:bg-sky-900/20 inline-block mb-3">
                <FolderOpen className="h-6 w-6 text-sky-600" />
              </div>
              <h3 className="font-bold text-gray-900 dark:text-gray-100">
                {col.name}
              </h3>
              {col.description && (
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">
                  {col.description}
                </p>
              )}
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-3">
                {col.is_public ? "Public" : "Private"}
              </p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
