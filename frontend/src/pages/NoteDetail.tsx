import { useState, lazy, Suspense } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

const TiptapEditor = lazy(() => import("@/components/editor/TiptapEditor"));
import {
  ArrowLeft,
  Star,
  Archive,
  Pencil,
  Trash2,
  FolderPlus,
  BookOpen,
  Sparkles,
  StickyNote,
  Hash,
  X,
  Check,
} from "lucide-react";
import { useNote, useUpdateNote, useDeleteNote, useNoteTags, useAddNoteTags, useRemoveNoteTag, useSummarizeNote, useGenerateNoteTitle } from "@/hooks/use-notes";
import { useCollections, useAddNoteToCollection } from "@/hooks/use-collections";
import { useToggleReadingList, useMarkAsRead } from "@/hooks/use-reading-list";
import { useHighlights } from "@/hooks/use-highlights";
import TextHighlighter from "@/components/content/TextHighlighter";
import ContentRenderer from "@/components/content/ContentRenderer";
import { timeAgo } from "@/lib/utils";

export default function NoteDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const noteId = id ?? "";
  const { data: note, isLoading, isError } = useNote(noteId);
  const { data: tags } = useNoteTags(noteId);
  const updateNote = useUpdateNote();
  const deleteNote = useDeleteNote();
  const summarize = useSummarizeNote();
  const generateTitle = useGenerateNoteTitle();
  const addTags = useAddNoteTags();
  const removeTag = useRemoveNoteTag();
  const { data: collections } = useCollections();
  const addToCollection = useAddNoteToCollection();
  const toggleReadingList = useToggleReadingList();
  const markAsRead = useMarkAsRead();
  const { data: highlights } = useHighlights(undefined, noteId);

  const [showCollections, setShowCollections] = useState(false);
  const [showAddTag, setShowAddTag] = useState(false);
  const [newTag, setNewTag] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-sky-600 text-lg">Loading...</div>
      </div>
    );
  }

  if (isError || !note) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 dark:text-gray-400">
          Note not found or you don&apos;t have access.
        </p>
        <Link to="/notes" className="text-sky-600 hover:underline mt-2 inline-block">
          Back to Notes
        </Link>
      </div>
    );
  }

  const handleDelete = () => {
    deleteNote.mutate(note.id, { onSuccess: () => navigate("/notes") });
  };

  const handleAddTag = () => {
    if (!newTag.trim()) return;
    addTags.mutate({ noteId: note.id, tags: [newTag.trim()] });
    setNewTag("");
    setShowAddTag(false);
  };

  const isOnReadingList = note.reading_status === "reading_list";
  const isRead = note.reading_status === "read";

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      {/* Back + Actions */}
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>

        <div className="flex items-center gap-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-full px-2 py-1 shadow-sm">
          <button
            onClick={() => updateNote.mutate({ id: note.id, is_favorite: !note.is_favorite })}
            className="p-1.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700"
            title={note.is_favorite ? "Unfavorite" : "Favorite"}
            aria-label={note.is_favorite ? "Unfavorite" : "Favorite"}
          >
            <Star className={`w-4 h-4 ${note.is_favorite ? "fill-yellow-400 text-yellow-400" : "text-gray-400"}`} />
          </button>
          <button
            onClick={() => updateNote.mutate({ id: note.id, is_archived: !note.is_archived })}
            className="p-1.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700"
            title={note.is_archived ? "Unarchive" : "Archive"}
            aria-label={note.is_archived ? "Unarchive" : "Archive"}
          >
            <Archive className={`w-4 h-4 ${note.is_archived ? "text-sky-500" : "text-gray-400"}`} />
          </button>
          <button
            onClick={() => toggleReadingList.mutate({ id: note.id, type: "note", add: !isOnReadingList })}
            className="p-1.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700"
            title={isOnReadingList ? "Remove from Reading List" : "Add to Reading List"}
            aria-label={isOnReadingList ? "Remove from Reading List" : "Add to Reading List"}
          >
            <BookOpen className={`w-4 h-4 ${isOnReadingList ? "text-sky-500" : "text-gray-400"}`} />
          </button>
          <button
            onClick={() => setShowCollections(!showCollections)}
            className="p-1.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700"
            title="Add to Collection"
            aria-label="Add to Collection"
          >
            <FolderPlus className="w-4 h-4 text-gray-400" />
          </button>
          <button
            onClick={() => {
              setEditTitle(note.title || "");
              setEditContent(note.content || "");
              setIsEditing(true);
            }}
            className="p-1.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700"
            title="Edit"
            aria-label="Edit"
          >
            <Pencil className="w-4 h-4 text-gray-400" />
          </button>
          {confirmDelete ? (
            <div className="flex items-center gap-1 ml-1">
              <button onClick={handleDelete} className="p-1.5 rounded-full bg-red-100 dark:bg-red-900/30">
                <Check className="w-4 h-4 text-red-500" />
              </button>
              <button onClick={() => setConfirmDelete(false)} className="p-1.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700">
                <X className="w-4 h-4 text-gray-400" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              className="p-1.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700"
              title="Delete"
              aria-label="Delete"
            >
              <Trash2 className="w-4 h-4 text-gray-400" />
            </button>
          )}
        </div>
      </div>

      {/* Collection picker dropdown */}
      {showCollections && collections && (
        <div className="mb-4 p-3 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Add to Collection</p>
          <div className="flex flex-wrap gap-2">
            {collections.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  addToCollection.mutate({ collectionId: c.id, noteIds: [note.id] });
                  setShowCollections(false);
                }}
                className="px-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 hover:border-sky-300 dark:hover:border-sky-600 hover:bg-sky-50 dark:hover:bg-sky-900/20 transition-colors"
              >
                {c.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {isEditing ? (
        <div className="mb-6 p-4 border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-800">
          <input
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            placeholder="Note title..."
            className="w-full px-3 py-2 mb-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-sky-500 focus:outline-none"
          />
          <Suspense fallback={<div className="h-48 animate-pulse bg-gray-100 dark:bg-gray-800 rounded-lg" />}>
            <TiptapEditor
              content={editContent}
              onChange={setEditContent}
              placeholder="Note content..."
            />
          </Suspense>
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setIsEditing(false)}
              className="px-4 py-2 text-sm rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                updateNote.mutate({
                  id: note.id,
                  title: editTitle.trim() || undefined,
                  content: editContent.trim() || undefined,
                });
                setIsEditing(false);
              }}
              className="px-4 py-2 text-sm rounded-lg bg-sky-600 text-white hover:bg-sky-700 transition-colors"
            >
              Save
            </button>
          </div>
        </div>
      ) : null}

      {/* Title */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <StickyNote className="w-5 h-5 text-amber-500" />
          <span className="text-xs text-gray-400">{timeAgo(note.created_at)}</span>
          {isRead && (
            <span className="inline-flex items-center px-2 py-0.5 text-[10px] rounded-full bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400">
              Read
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {note.title || "Untitled Note"}
          </h1>
          {!note.title && (
            <button
              onClick={() => generateTitle.mutate(note.id)}
              disabled={generateTitle.isPending}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-lg bg-sky-50 dark:bg-sky-900/20 text-sky-600 dark:text-sky-400 hover:bg-sky-100 dark:hover:bg-sky-900/40 transition-colors"
            >
              <Sparkles className="w-3 h-3" />
              {generateTitle.isPending ? "Generating..." : "Auto-title"}
            </button>
          )}
        </div>
      </div>

      {/* AI Summary */}
      {note.summary ? (
        <div className="mb-4 p-3 bg-sky-50 dark:bg-sky-900/20 border border-sky-200 dark:border-sky-800 rounded-lg">
          <p className="text-xs font-medium text-sky-600 dark:text-sky-400 mb-1">AI Summary</p>
          <p className="text-sm text-gray-700 dark:text-gray-300">{note.summary}</p>
        </div>
      ) : (
        <button
          onClick={() => summarize.mutate(note.id)}
          disabled={summarize.isPending}
          className="mb-4 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-sky-200 dark:border-sky-800 text-sky-600 dark:text-sky-400 hover:bg-sky-50 dark:hover:bg-sky-900/20 transition-colors"
        >
          <Sparkles className="w-3.5 h-3.5" />
          {summarize.isPending ? "Summarizing..." : "Generate Summary"}
        </button>
      )}

      {/* Tags */}
      <div className="flex items-center gap-2 flex-wrap mb-6">
        {tags?.map((tag) => (
          <span
            key={tag.id}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-sky-50 dark:bg-sky-900/20 text-sky-600 dark:text-sky-400"
          >
            <Hash className="w-3 h-3" />
            {tag.name}
            <button
              onClick={() => removeTag.mutate({ noteId: note.id, tagId: tag.id })}
              className="ml-0.5 hover:text-red-500"
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}
        {showAddTag ? (
          <form
            onSubmit={(e) => { e.preventDefault(); handleAddTag(); }}
            className="inline-flex items-center gap-1"
          >
            <input
              type="text"
              value={newTag}
              onChange={(e) => setNewTag(e.target.value)}
              placeholder="Tag name"
              className="px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 w-24"
              autoFocus
            />
            <button type="submit" className="p-1 text-green-500 hover:text-green-600">
              <Check className="w-3.5 h-3.5" />
            </button>
            <button type="button" onClick={() => setShowAddTag(false)} className="p-1 text-gray-400">
              <X className="w-3.5 h-3.5" />
            </button>
          </form>
        ) : (
          <button
            onClick={() => setShowAddTag(true)}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full border border-dashed border-gray-300 dark:border-gray-600 text-gray-400 hover:border-sky-400 hover:text-sky-500 transition-colors"
          >
            + Add Tag
          </button>
        )}
      </div>

      {/* Content */}
      {note.content && (
        <TextHighlighter noteId={note.id} highlights={highlights}>
          <ContentRenderer content={note.content} />
        </TextHighlighter>
      )}

      {/* Mark as read */}
      {isOnReadingList && (
        <div className="mt-6 flex justify-center">
          <button
            onClick={() => markAsRead.mutate({ id: note.id, type: "note" })}
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-green-600 hover:bg-green-700 text-white text-sm font-medium transition-colors"
          >
            <Check className="w-4 h-4" />
            Mark as Read
          </button>
        </div>
      )}
    </div>
  );
}
