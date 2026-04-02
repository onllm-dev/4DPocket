import { useState } from "react";
import { Share2, Link2, Copy, Check, X, Loader2, Users } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

interface ShareDialogProps {
  itemId?: string;
  collectionId?: string;
  onClose: () => void;
}

export function ShareDialog({ itemId, collectionId, onClose }: ShareDialogProps) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"viewer" | "editor">("viewer");
  const [publicLink, setPublicLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const qc = useQueryClient();

  const createShare = useMutation({
    mutationFn: (data: any) => api.post("/api/v1/shares", data),
    onSuccess: (data: any) => {
      if (data.public_token) {
        setPublicLink(`${window.location.origin}/public/${data.public_token}`);
      }
      qc.invalidateQueries({ queryKey: ["shares"] });
    },
  });

  const handleShareWithUser = async () => {
    if (!email.trim()) return;
    await createShare.mutateAsync({
      share_type: itemId ? "item" : "collection",
      item_id: itemId || null,
      collection_id: collectionId || null,
      recipient_email: email.trim(),
      recipient_role: role,
    });
    setEmail("");
  };

  const handleGenerateLink = async () => {
    await createShare.mutateAsync({
      share_type: itemId ? "item" : "collection",
      item_id: itemId || null,
      collection_id: collectionId || null,
      public: true,
    });
  };

  const copyLink = () => {
    if (publicLink) {
      navigator.clipboard.writeText(publicLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 shadow-xl p-6 max-w-md w-full animate-fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Share2 className="w-5 h-5 text-sky-600" />
            <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">Share</h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Share with user */}
        <div className="mb-5">
          <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            <Users className="w-4 h-4" /> Share with user
          </label>
          <div className="flex gap-2">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
              className="flex-1 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-sky-500 focus:outline-none"
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as "viewer" | "editor")}
              className="px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 cursor-pointer"
            >
              <option value="viewer">Viewer</option>
              <option value="editor">Editor</option>
            </select>
          </div>
          <button
            onClick={handleShareWithUser}
            disabled={!email.trim() || createShare.isPending}
            className="mt-2 w-full py-2 bg-sky-600 text-white rounded-lg text-sm font-medium hover:bg-sky-700 disabled:opacity-50 cursor-pointer transition-all flex items-center justify-center gap-2"
          >
            {createShare.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Share
          </button>
        </div>

        {/* Public link */}
        <div className="border-t border-gray-200 dark:border-gray-800 pt-4">
          <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            <Link2 className="w-4 h-4" /> Public link
          </label>
          {publicLink ? (
            <div className="flex gap-2">
              <input
                type="text"
                value={publicLink}
                readOnly
                className="flex-1 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-xs font-mono text-gray-900 dark:text-gray-100"
              />
              <button
                onClick={copyLink}
                className="px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 cursor-pointer transition-all"
              >
                {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4 text-gray-500" />}
              </button>
            </div>
          ) : (
            <button
              onClick={handleGenerateLink}
              disabled={createShare.isPending}
              className="w-full py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium hover:bg-gray-200 dark:hover:bg-gray-700 cursor-pointer transition-all"
            >
              Generate public link
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
