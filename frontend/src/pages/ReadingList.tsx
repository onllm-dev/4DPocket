import { useState } from "react";
import { BookOpen, CheckCircle, BookMarked } from "lucide-react";
import { useReadingList, useReadList, useMarkAsRead } from "@/hooks/use-reading-list";
import { useNotes } from "@/hooks/use-notes";
import { BookmarkCard } from "@/components/bookmark/BookmarkCard";
import NoteCard from "@/components/bookmark/NoteCard";

type Tab = "reading" | "read";

export default function ReadingList() {
  const [tab, setTab] = useState<Tab>("reading");
  const { data: readingItems, isLoading: loadingReading } = useReadingList();
  const { data: readItems, isLoading: loadingRead } = useReadList();
  const { data: allNotes } = useNotes();
  const markAsRead = useMarkAsRead();

  const readingNotes = allNotes?.filter((n) => n.reading_status === "reading_list") || [];
  const readNotes = allNotes?.filter((n) => n.reading_status === "read") || [];

  const isLoading = tab === "reading" ? loadingReading : loadingRead;
  const items = tab === "reading" ? readingItems : readItems;
  const notes = tab === "reading" ? readingNotes : readNotes;

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <BookMarked className="w-6 h-6 text-sky-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Reading List</h1>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 dark:bg-gray-800 rounded-lg p-1 w-fit">
        <button
          onClick={() => setTab("reading")}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            tab === "reading"
              ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm"
              : "text-gray-500 dark:text-gray-400 hover:text-gray-700"
          }`}
        >
          <BookOpen className="w-4 h-4" />
          To Read
          {readingItems && (
            <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-sky-100 dark:bg-sky-900/30 text-sky-600 dark:text-sky-400">
              {(readingItems?.length || 0) + readingNotes.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setTab("read")}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            tab === "read"
              ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm"
              : "text-gray-500 dark:text-gray-400 hover:text-gray-700"
          }`}
        >
          <CheckCircle className="w-4 h-4" />
          Read
          {readItems && (
            <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400">
              {(readItems?.length || 0) + readNotes.length}
            </span>
          )}
        </button>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-pulse text-sky-600">Loading...</div>
        </div>
      ) : (!items?.length && !notes?.length) ? (
        <div className="text-center py-16">
          <BookOpen className="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
          <p className="text-gray-500 dark:text-gray-400 text-lg">
            {tab === "reading"
              ? "Your reading list is empty"
              : "No read items"}
          </p>
          <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">
            {tab === "reading"
              ? "Add items or notes to your reading list from their detail pages"
              : "Items you mark as read will appear here"}
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Items */}
          {items && items.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">
                Items ({items.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {items.map((item) => (
                  <div key={item.id} className="relative">
                    <BookmarkCard item={item} />
                    {tab === "reading" && (
                      <button
                        onClick={() => markAsRead.mutate({ id: item.id, type: "item" })}
                        className="absolute top-2 right-2 inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-green-600 text-white hover:bg-green-700 shadow transition-colors z-10"
                      >
                        <CheckCircle className="w-3 h-3" />
                        Done
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Notes */}
          {notes && notes.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">
                Notes ({notes.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {notes.map((note) => (
                  <div key={note.id} className="relative">
                    <NoteCard note={note} />
                    {tab === "reading" && (
                      <button
                        onClick={() => markAsRead.mutate({ id: note.id, type: "note" })}
                        className="absolute top-2 right-2 inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-green-600 text-white hover:bg-green-700 shadow transition-colors z-10"
                      >
                        <CheckCircle className="w-3 h-3" />
                        Done
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
