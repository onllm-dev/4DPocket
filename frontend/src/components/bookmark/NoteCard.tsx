import { Link } from "react-router-dom";
import { Star, StickyNote, BookOpen } from "lucide-react";
import { useUpdateNote, type Note } from "@/hooks/use-notes";
import { timeAgo } from "@/lib/utils";

interface NoteCardProps {
  note: Note;
  variant?: "grid" | "list" | "compact";
}

function stripHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  return doc.body.textContent || "";
}

export default function NoteCard({ note, variant = "grid" }: NoteCardProps) {
  const updateNote = useUpdateNote();

  const toggleFavorite = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    updateNote.mutate({ id: note.id, is_favorite: !note.is_favorite });
  };

  const contentPreview = note.content ? stripHtml(note.content).slice(0, 200) : "";

  if (variant === "compact") {
    return (
      <Link
        to={`/notes/${note.id}`}
        className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
      >
        <StickyNote className="w-4 h-4 text-amber-500 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
            {note.title || "Untitled Note"}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">{timeAgo(note.created_at)}</p>
        </div>
        {note.reading_status === "reading_list" && (
          <BookOpen className="w-3.5 h-3.5 text-sky-500 shrink-0" />
        )}
      </Link>
    );
  }

  return (
    <Link
      to={`/notes/${note.id}`}
      className="group block rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/50 hover:border-sky-300 dark:hover:border-sky-600 hover:shadow-md transition-all overflow-hidden"
    >
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400">
              <StickyNote className="w-3 h-3" />
              Note
            </span>
            {note.reading_status === "reading_list" && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full bg-sky-50 dark:bg-sky-900/20 text-sky-600 dark:text-sky-400">
                <BookOpen className="w-3 h-3" />
                Reading List
              </span>
            )}
          </div>
          <button
            onClick={toggleFavorite}
            aria-label={note.is_favorite ? "Unfavorite" : "Favorite"}
            className="shrink-0 p-1 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <Star
              className={`w-4 h-4 ${
                note.is_favorite
                  ? "fill-yellow-400 text-yellow-400"
                  : "text-gray-300 dark:text-gray-600"
              }`}
            />
          </button>
        </div>

        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 line-clamp-2 mb-1">
          {note.title || "Untitled Note"}
        </h3>

        {note.summary && (
          <p className="text-xs text-sky-600 dark:text-sky-400 line-clamp-2 mb-2">
            {note.summary}
          </p>
        )}

        {contentPreview && (
          <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-3">
            {contentPreview}
          </p>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2.5 border-t border-gray-100 dark:border-gray-700/50 bg-gray-50/50 dark:bg-gray-800/30">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-gray-400 dark:text-gray-500">
            {timeAgo(note.created_at)}
          </span>
        </div>
      </div>
    </Link>
  );
}
