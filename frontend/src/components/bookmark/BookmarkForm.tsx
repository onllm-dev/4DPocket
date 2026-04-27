import { useState, useRef, useCallback, lazy, Suspense } from "react";
import { Link2, FileText, Loader2, X, Plus, Trash2, Mic } from "lucide-react";
import { useCreateItem, useUpdateItem } from "@/hooks/use-items";
import { api, apiFetch } from "@/api/client";

const TiptapEditor = lazy(() => import("@/components/editor/TiptapEditor"));

interface Item {
  id: string;
  title: string | null;
  content: string | null;
}

interface BookmarkFormProps {
  onClose?: () => void;
  onCreated?: (created: { id: string }) => void;
}

interface EditBookmarkFormProps {
  item: Item;
  onClose?: () => void;
  onUpdated?: () => void;
}

export function BookmarkForm({ onClose, onCreated }: BookmarkFormProps) {
  const [url, setUrl] = useState("");
  const [extraUrls, setExtraUrls] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [mode, setMode] = useState<"url" | "note">("url");
  const [content, setContent] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const createItem = useCreateItem();

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
        if (blob.size < 1000) return;

        setIsTranscribing(true);
        try {
          const formData = new FormData();
          formData.append("file", blob, "voice-note.webm");
          const res = await apiFetch("/api/v1/ai/transcribe", {
            method: "POST",
            headers: {},
            body: formData,
          });
          if (res.ok) {
            const data = await res.json();
            if (data.text) {
              setContent((prev) => (prev ? prev + "\n\n" + data.text : data.text));
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
      setVoiceError("Microphone access denied.");
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  const addExtraUrl = () => setExtraUrls((prev) => [...prev, ""]);
  const removeExtraUrl = (index: number) =>
    setExtraUrls((prev) => prev.filter((_, i) => i !== index));
  const updateExtraUrl = (index: number, value: string) =>
    setExtraUrls((prev) => prev.map((u, i) => (i === index ? value : u)));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      let created: { id: string };
      if (mode === "url") {
        if (!url.trim()) return;
        created = await createItem.mutateAsync({ url: url.trim() });
        const validExtras = extraUrls.map((u) => u.trim()).filter(Boolean);
        for (const extraUrl of validExtras) {
          await api.post(`/api/v1/items/${created.id}/links`, { url: extraUrl });
        }
      } else {
        if (!content.trim()) return;
        created = await createItem.mutateAsync({ title: title.trim(), content: content.trim() });
      }
      setUrl("");
      setExtraUrls([]);
      setTitle("");
      setContent("");
      onCreated?.(created);
      onClose?.();
    } catch {
      // Error handled by mutation state
    }
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 shadow-xl p-6 max-w-lg w-full animate-fade-in">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">Add to Pocket</h2>
        {onClose && (
          <button onClick={onClose} aria-label="Close" className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        )}
      </div>

      <div className="flex gap-2 mb-5">
        <button
          onClick={() => setMode("url")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer ${
            mode === "url"
              ? "bg-sky-600 text-white shadow-sm"
              : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"
          }`}
        >
          <Link2 className="w-4 h-4" />
          URL
        </button>
        <button
          onClick={() => setMode("note")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer ${
            mode === "note"
              ? "bg-sky-600 text-white shadow-sm"
              : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"
          }`}
        >
          <FileText className="w-4 h-4" />
          Note
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === "url" ? (
          <div className="space-y-3">
            <div className="relative">
              <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="Paste a URL..."
                className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
                autoFocus
                required
              />
            </div>
            {extraUrls.map((extraUrl, index) => (
              <div key={index} className="relative flex items-center gap-2">
                <div className="relative flex-1">
                  <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="url"
                    value={extraUrl}
                    onChange={(e) => updateExtraUrl(index, e.target.value)}
                    placeholder="Additional URL..."
                    className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => removeExtraUrl(index)}
                  aria-label="Remove URL"
                  className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-red-500 transition-colors cursor-pointer"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={addExtraUrl}
              className="inline-flex items-center gap-1.5 text-sm text-sky-600 hover:text-sky-700 font-medium transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              Add another URL
            </button>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Note title..."
                className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
                autoFocus
              />
              <button
                type="button"
                onClick={isRecording ? stopRecording : startRecording}
                disabled={isTranscribing}
                className={`p-2.5 rounded-xl text-sm font-medium transition-all duration-200 cursor-pointer disabled:opacity-50 ${
                  isRecording
                    ? "bg-red-500 text-white shadow-md shadow-red-500/20"
                    : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:shadow-md"
                }`}
                aria-label={isRecording ? "Stop recording" : "Start voice note"}
              >
                {isRecording ? (
                  <span className="relative flex h-4 w-4">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75" />
                    <span className="relative inline-flex rounded-full h-4 w-4 bg-white" />
                  </span>
                ) : (
                  <Mic className="w-4 h-4" />
                )}
              </button>
            </div>
            {voiceError && (
              <p className="text-xs text-red-500 mb-1">{voiceError}</p>
            )}
            {isTranscribing && (
              <span className="flex items-center gap-1.5 text-xs text-sky-600">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Transcribing...
              </span>
            )}
            <Suspense fallback={<div className="h-48 animate-pulse bg-gray-100 dark:bg-gray-800 rounded-lg" />}>
              <TiptapEditor
                content={content}
                onChange={setContent}
                placeholder="Write your note..."
              />
            </Suspense>
          </>
        )}

        <button
          type="submit"
          disabled={createItem.isPending}
          className="w-full py-3 bg-sky-600 text-white rounded-xl font-medium hover:bg-sky-700 active:scale-[0.98] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer flex items-center justify-center gap-2"
        >
          {createItem.isPending ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Saving...
            </>
          ) : (
            "Save to Pocket"
          )}
        </button>

        {createItem.isError && (
          <p className={`text-sm text-center ${
            createItem.error?.message?.toLowerCase().includes("already saved")
              ? "text-amber-600 dark:text-amber-400"
              : "text-red-500"
          }`}>
            {createItem.error?.message || "Failed to save. Please try again."}
          </p>
        )}
      </form>
    </div>
  );
}

export function EditBookmarkForm({ item, onClose, onUpdated }: EditBookmarkFormProps) {
  const [title, setTitle] = useState(item.title ?? "");
  const [content, setContent] = useState(item.content ?? "");
  const updateItem = useUpdateItem();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await updateItem.mutateAsync({
        id: item.id,
        title: title.trim() || undefined,
        content: content.trim() || undefined,
      });
      onUpdated?.();
      onClose?.();
    } catch {
      // Error handled by mutation state
    }
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 shadow-xl p-6 max-w-lg w-full animate-fade-in">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">Edit Item</h2>
        {onClose && (
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title..."
          className="w-full px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
          autoFocus
        />
        <Suspense fallback={<div className="h-48 animate-pulse bg-gray-100 dark:bg-gray-800 rounded-lg" />}>
          <TiptapEditor
            content={content}
            onChange={setContent}
            placeholder="Write content..."
          />
        </Suspense>

        <button
          type="submit"
          disabled={updateItem.isPending}
          className="w-full py-3 bg-sky-600 text-white rounded-xl font-medium hover:bg-sky-700 active:scale-[0.98] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer flex items-center justify-center gap-2"
        >
          {updateItem.isPending ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Saving...
            </>
          ) : (
            "Save Changes"
          )}
        </button>

        {updateItem.isError && (
          <p className="text-red-500 text-sm text-center">
            {updateItem.error?.message || "Failed to save. Please try again."}
          </p>
        )}
      </form>
    </div>
  );
}
