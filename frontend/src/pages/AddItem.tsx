import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, CheckCircle, Loader2 } from "lucide-react";
import { BookmarkForm } from "@/components/bookmark/BookmarkForm";
import { useCreateItem } from "@/hooks/use-items";

export default function AddItem() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const createItem = useCreateItem();
  const [shareState, setShareState] = useState<"idle" | "saving" | "success" | "error">("idle");

  useEffect(() => {
    const sharedUrl = searchParams.get("url");
    const sharedText = searchParams.get("text");
    const sharedTitle = searchParams.get("title");

    // Extract URL from text if no direct url param (common when sharing from mobile apps)
    const urlToSave = sharedUrl || sharedText?.match(/https?:\/\/\S+/)?.[0];

    if (!urlToSave) return;

    setShareState("saving");
    createItem.mutate(
      { url: urlToSave, title: sharedTitle || undefined },
      {
        onSuccess: () => {
          setShareState("success");
          setTimeout(() => navigate("/"), 1500);
        },
        onError: () => {
          setShareState("error");
        },
      }
    );
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (shareState === "saving") {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-6">
        <Loader2 className="h-10 w-10 animate-spin text-[#0096C7]" />
        <p className="text-gray-600 dark:text-gray-400 text-sm">Tossing it into your pocket...</p>
      </div>
    );
  }

  if (shareState === "success") {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-6">
        <div className="animate-pocket-drop">
          <CheckCircle className="h-10 w-10 text-[#0096C7]" />
        </div>
        <p className="text-gray-900 dark:text-gray-100 font-medium">Dropped into your pocket!</p>
        <p className="text-gray-500 dark:text-gray-400 text-sm">Redirecting...</p>
      </div>
    );
  }

  if (shareState === "error") {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-6">
        <p className="text-red-500 font-medium">Failed to save. Please try again.</p>
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-[#0096C7] hover:underline cursor-pointer"
        >
          Go back
        </button>
      </div>
    );
  }

  return (
    <div className="animate-fade-in p-6 max-w-2xl mx-auto">
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 mb-6 p-2 -ml-2 rounded-xl hover:bg-sky-50 dark:hover:bg-gray-800 transition-all duration-200 cursor-pointer"
      >
        <ArrowLeft className="h-4 w-4" />
        Back
      </button>

      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-1">
          Toss it into your pocket
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 italic">
          Save anything — it'll be there when you need it.
        </p>
      </div>

      <div className="flex items-center justify-center min-h-[50vh]">
        <BookmarkForm onClose={() => navigate(-1)} />
      </div>
    </div>
  );
}
