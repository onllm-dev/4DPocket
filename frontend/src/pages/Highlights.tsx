import { useState } from "react";
import { Link } from "react-router-dom";
import { Highlighter, Trash2, Search, X } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { timeAgo } from "@/lib/utils";

interface HighlightItem {
  id: string;
  item_id: string;
  text: string;
  note: string | null;
  color: string;
  created_at: string;
}

const COLORS = ["yellow", "green", "blue", "red", "purple"];
const COLOR_MAP: Record<string, string> = {
  yellow: "bg-yellow-100 dark:bg-yellow-900/30 border-yellow-300 dark:border-yellow-700",
  green: "bg-green-100 dark:bg-green-900/30 border-green-300 dark:border-green-700",
  blue: "bg-blue-100 dark:bg-blue-900/30 border-blue-300 dark:border-blue-700",
  red: "bg-red-100 dark:bg-red-900/30 border-red-300 dark:border-red-700",
  purple: "bg-purple-100 dark:bg-purple-900/30 border-purple-300 dark:border-purple-700",
};

export default function Highlights() {
  const qc = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [filterColor, setFilterColor] = useState<string | null>(null);

  const { data: highlights, isLoading } = useQuery<HighlightItem[]>({
    queryKey: ["highlights", searchQuery],
    queryFn: () => searchQuery
      ? api.get(`/api/v1/highlights/search?q=${encodeURIComponent(searchQuery)}`)
      : api.get("/api/v1/highlights"),
  });

  const deleteHighlight = useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/highlights/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["highlights"] }),
  });

  const filtered = filterColor
    ? highlights?.filter((h) => h.color === filterColor)
    : highlights;

  return (
    <div className="animate-fade-in max-w-5xl mx-auto px-4">
      <div className="flex items-center gap-3 mb-6">
        <Highlighter className="w-6 h-6 text-sky-600" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Highlights</h1>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search highlights..."
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm"
          />
        </div>
        <div className="flex gap-1 items-center">
          {COLORS.map((c) => (
            <button
              key={c}
              onClick={() => setFilterColor(filterColor === c ? null : c)}
              className={`w-8 h-8 rounded-lg border-2 transition-all cursor-pointer ${COLOR_MAP[c]} ${filterColor === c ? "ring-2 ring-sky-500 ring-offset-1 dark:ring-offset-gray-950" : ""}`}
            />
          ))}
          {filterColor !== null && (
            <button
              onClick={() => setFilterColor(null)}
              className="ml-1 p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-all cursor-pointer"
              aria-label="Clear color filter"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-2">
              <div className="h-4 w-full animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
              <div className="h-3 w-3/4 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
              <div className="h-3 w-16 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
            </div>
          ))}
        </div>
      ) : !filtered?.length ? (
        <div className="text-center py-16 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <Highlighter className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-700 dark:text-gray-300 text-lg font-medium mb-1">No highlights</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mb-4">Select text on any saved item to create a highlight.</p>
          <Link to="/knowledge" className="text-sm text-sky-600 hover:text-sky-700 font-medium">Browse your items</Link>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((h) => (
            <div key={h.id} className={`rounded-xl border p-4 ${COLOR_MAP[h.color] || COLOR_MAP.yellow}`}>
              <p className="text-sm text-gray-900 dark:text-gray-100 leading-relaxed">{h.text}</p>
              {h.note && (
                <p className="text-xs text-gray-600 dark:text-gray-300 mt-2 italic">{h.note}</p>
              )}
              <div className="flex items-center justify-between mt-3">
                <span className="text-[10px] text-gray-500 dark:text-gray-400">{timeAgo(h.created_at)}</span>
                <button onClick={() => deleteHighlight.mutate(h.id)} aria-label="Delete highlight" className="p-1 text-gray-400 hover:text-red-500 transition-colors cursor-pointer">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
