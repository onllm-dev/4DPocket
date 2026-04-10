import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Share2, Inbox, CheckCircle, Clock, BookOpen, Library } from "lucide-react";
import { api } from "@/api/client";

type SharedWithMeItem = {
  share_id: string;
  share_type: "item" | "collection" | "tag";
  item_id: string | null;
  collection_id: string | null;
  tag_id: string | null;
  role: "viewer" | "editor";
  accepted: boolean;
  owner_id: string;
  created_at: string;
};

function RoleBadge({ role }: { role: "viewer" | "editor" }) {
  return (
    <span
      className={`text-xs font-medium px-2 py-0.5 rounded-full ${
        role === "editor"
          ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300"
          : "bg-sky-100 text-sky-800 dark:bg-sky-900/30 dark:text-sky-300"
      }`}
    >
      {role}
    </span>
  );
}

function ShareTypeIcon({ type }: { type: string }) {
  if (type === "collection") return <Library className="w-5 h-5 text-purple-500" />;
  if (type === "tag") return <BookOpen className="w-5 h-5 text-green-500" />;
  return <Share2 className="w-5 h-5 text-sky-500" />;
}

function SharedCard({ share }: { share: SharedWithMeItem }) {
  const queryClient = useQueryClient();

  const acceptMutation = useMutation({
    mutationFn: () => api.post(`/api/v1/shares/${share.share_id}/accept`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["shared-with-me"] });
    },
  });

  const label =
    share.share_type === "item"
      ? "Item"
      : share.share_type === "collection"
      ? "Collection"
      : "Tag";

  const resourceId =
    share.item_id ?? share.collection_id ?? share.tag_id ?? "Unknown";

  return (
    <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <ShareTypeIcon type={share.share_type} />
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
          {label}
        </span>
        <RoleBadge role={share.role} />
        {share.accepted ? (
          <span className="ml-auto flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
            <CheckCircle className="w-3.5 h-3.5" /> Accepted
          </span>
        ) : (
          <span className="ml-auto flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
            <Clock className="w-3.5 h-3.5" /> Pending
          </span>
        )}
      </div>

      <p className="text-sm text-gray-500 dark:text-gray-400 font-mono truncate">
        ID: {resourceId}
      </p>

      <p className="text-xs text-gray-400 dark:text-gray-500">
        Shared {new Date(share.created_at).toLocaleDateString()}
      </p>

      {!share.accepted && (
        <button
          onClick={() => acceptMutation.mutate()}
          disabled={acceptMutation.isPending}
          className="mt-1 w-full rounded-xl bg-[#0096C7] hover:bg-[#007BA8] disabled:opacity-60 text-white text-sm font-medium py-2 transition-colors"
        >
          {acceptMutation.isPending ? "Accepting…" : "Accept"}
        </button>
      )}
    </div>
  );
}

export default function SharedWithMe() {
  const { data: shares, isLoading } = useQuery<SharedWithMeItem[]>({
    queryKey: ["shared-with-me"],
    queryFn: () => api.get("/api/v1/shares/shared-with-me"),
  });

  return (
    <div className="animate-fade-in max-w-4xl mx-auto px-4 md:px-6">
      <div className="flex items-center gap-3 mb-6">
        <Share2 className="w-6 h-6 text-sky-600" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Shared with Me</h1>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 space-y-3"
            >
              <div className="h-3 w-24 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
              <div className="h-4 w-full animate-pulse bg-gray-200 dark:bg-gray-700 rounded" />
              <div className="h-3 w-20 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
            </div>
          ))}
        </div>
      ) : !shares || shares.length === 0 ? (
        <div className="text-center py-16 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <Inbox className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-700 dark:text-gray-300 text-lg font-medium mb-1">No shared items</p>
          <p className="text-sm text-gray-400 dark:text-gray-500">
            Items shared with you by other users will appear here.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {shares.map((share) => (
            <SharedCard key={share.share_id} share={share} />
          ))}
        </div>
      )}
    </div>
  );
}
