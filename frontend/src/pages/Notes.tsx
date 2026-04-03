import { useState, useRef, useCallback, lazy, Suspense } from "react";
import { Link } from "react-router-dom";
import { FileText, Pencil, Plus, Trash2, X, Mic, Loader2 } from "lucide-react";

const TiptapEditor = lazy(() => import("@/components/editor/TiptapEditor"));
import { api, apiFetch } from "@/api/client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { timeAgo } from "@/lib/utils";

interface Note {
  id: string;
  title: string | null;
  content: string | null;
  created_at: string;
}

export default function Notes() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    setVoiceError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        if (blob.size < 1000) return; // Too short

        setIsTranscribing(true);
        try {
          const formData = new FormData();
          formData.append("file", blob, "voice-note.webm");
          const res = await apiFetch("/api/v1/ai/transcribe", {
            method: "POST",
            headers: {}, // Let browser set content-type for FormData
            body: formData,
          });
          if (res.ok) {
            const data = await res.json();
            if (data.text) {
              setContent((prev) => (prev ? prev + "\n\n" + data.text : data.text));
              if (!showForm) setShowForm(true);
            }
          }
        } catch {
          setVoiceError("Transcription failed. Please try again.");
        } finally {
          setIsTranscribing(false);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch {
      setVoiceError("Microphone access denied");
    }
  }, [showForm]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  const { data: notes, isLoading } = useQuery<Note[]>({
    queryKey: ["notes"],
    queryFn: () => api.get("/api/v1/notes"),
  });

  const createNote = useMutation({
    mutationFn: (data: { title?: string; content: string }) =>
      api.post("/api/v1/notes", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notes"] });
      setTitle("");
      setContent("");
      setShowForm(false);
    },
  });

  const updateNote = useMutation({
    mutationFn: ({ id, ...data }: { id: string; title?: string; content: string }) =>
      api.patch(`/api/v1/notes/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notes"] });
      setEditingId(null);
    },
  });

  const deleteNote = useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/notes/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notes"] });
      setDeletingId(null);
    },
  });

  const startEdit = (note: Note) => {
    setEditingId(note.id);
    setEditTitle(note.title || "");
    setEditContent(note.content || "");
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editContent.trim() || !editingId) return;
    updateNote.mutate({
      id: editingId,
      title: editTitle.trim() || undefined,
      content: editContent.trim(),
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;
    createNote.mutate({
      title: title.trim() || undefined,
      content: content.trim(),
    });
  };

  return (
    <div className="animate-fade-in p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <FileText className="h-6 w-6 text-sky-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Notes
          </h1>
        </div>
        <div className="flex items-center gap-2">
          {isTranscribing && (
            <span className="flex items-center gap-1.5 text-xs text-sky-600">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Transcribing...
            </span>
          )}
          <button
            onClick={isRecording ? stopRecording : startRecording}
            disabled={isTranscribing}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 cursor-pointer disabled:opacity-50 min-h-[44px] ${
              isRecording
                ? "bg-red-500 text-white shadow-md shadow-red-500/20"
                : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-md"
            }`}
            aria-label={isRecording ? "Stop recording" : "Start voice note"}
          >
            {isRecording ? (
              <>
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75" />
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-white" />
                </span>
                <span className="hidden sm:inline">Recording...</span>
              </>
            ) : (
              <>
                <Mic className="h-4 w-4" />
                <span className="hidden sm:inline">Voice</span>
              </>
            )}
          </button>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-sky-600 text-white rounded-lg text-sm font-medium hover:shadow-md transition-all duration-200 cursor-pointer"
          >
            <Plus className="h-4 w-4" />
            New Note
          </button>
        </div>
      </div>
      {voiceError && (
        <p className="text-xs text-red-500 mt-1 mb-2">{voiceError}</p>
      )}

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="mb-8 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5 space-y-3"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100">
              Create Note
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
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Note title (optional)"
            autoFocus
            className="w-full px-4 py-2.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-600"
          />
          <Suspense fallback={<div className="h-48 animate-pulse bg-gray-100 dark:bg-gray-800 rounded-lg" />}>
            <TiptapEditor
              content={content}
              onChange={setContent}
              placeholder="Write a note..."
            />
          </Suspense>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={createNote.isPending || !content.trim()}
              className="px-4 py-2 bg-sky-600 text-white rounded-lg text-sm font-medium hover:shadow-md transition-all duration-200 cursor-pointer disabled:opacity-50"
            >
              {createNote.isPending ? "Saving..." : "Save Note"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded-lg text-sm cursor-pointer hover:shadow-md transition-all duration-200"
            >
              Cancel
            </button>
          </div>
          {createNote.isError && <p className="text-sm text-red-500 mt-2">Failed to save note. Please try again.</p>}
        </form>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded animate-pulse bg-gray-200 dark:bg-gray-700" />
                <div className="h-4 w-32 animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="ml-auto h-3 w-16 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
              </div>
              <div className="pl-6 space-y-1.5">
                <div className="h-3 w-full animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
                <div className="h-3 w-3/4 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : !notes || notes.length === 0 ? (
        <div className="text-center py-16 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <FileText className="h-12 w-12 text-[#0096C7]/20 dark:text-sky-900 mx-auto mb-4" />
          <p className="text-gray-700 dark:text-gray-300 text-lg font-medium mb-1">
            No notes yet
          </p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mb-6">
            Capture your thoughts, ideas, and voice memos
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-sky-600 text-white rounded-lg font-medium hover:shadow-md transition-all duration-200 cursor-pointer"
          >
            <Plus className="h-4 w-4" />
            Create your first note
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {notes.map((note) => (
            <div
              key={note.id}
              className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-4 hover:shadow-md transition-all duration-200"
            >
              {editingId === note.id ? (
                <form onSubmit={handleUpdate} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100">
                      Edit Note
                    </h2>
                    <button
                      type="button"
                      onClick={() => setEditingId(null)}
                      className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 transition-all duration-200 cursor-pointer"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    placeholder="Note title (optional)"
                    autoFocus
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-600"
                  />
                  <Suspense fallback={<div className="h-48 animate-pulse bg-gray-100 dark:bg-gray-800 rounded-lg" />}>
                    <TiptapEditor
                      content={editContent}
                      onChange={setEditContent}
                      placeholder="Write a note..."
                    />
                  </Suspense>
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={updateNote.isPending || !editContent.trim()}
                      className="px-4 py-2 bg-sky-600 text-white rounded-lg text-sm font-medium hover:shadow-md transition-all duration-200 cursor-pointer disabled:opacity-50"
                    >
                      {updateNote.isPending ? "Saving..." : "Save Changes"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingId(null)}
                      className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded-lg text-sm cursor-pointer hover:shadow-md transition-all duration-200"
                    >
                      Cancel
                    </button>
                  </div>
                  {updateNote.isError && <p className="text-sm text-red-500 mt-2">Failed to update note. Please try again.</p>}
                </form>
              ) : deletingId === note.id ? (
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    Delete this note?
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => deleteNote.mutate(note.id)}
                      disabled={deleteNote.isPending}
                      className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:shadow-md transition-all duration-200 cursor-pointer disabled:opacity-50"
                    >
                      {deleteNote.isPending ? "Deleting..." : "Delete"}
                    </button>
                    <button
                      onClick={() => setDeletingId(null)}
                      className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded-lg text-sm cursor-pointer hover:shadow-md transition-all duration-200"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between mb-2">
                    <Link to={`/notes/${note.id}`} className="flex items-center gap-2 hover:text-sky-600 transition-colors">
                      <FileText className="h-4 w-4 text-sky-600" />
                      <h3 className="font-bold text-sm text-gray-900 dark:text-gray-100 hover:text-sky-600">
                        {note.title || "Untitled Note"}
                      </h3>
                    </Link>
                    <div className="flex items-center gap-1">
                      <span className="text-xs text-gray-600 dark:text-gray-400 mr-2">
                        {timeAgo(note.created_at)}
                      </span>
                      <button
                        onClick={() => startEdit(note)}
                        className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => setDeletingId(note.id)}
                        className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-4 pl-6">
                    {note.content ? new DOMParser().parseFromString(note.content, "text/html").body.textContent || "" : ""}
                  </p>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
