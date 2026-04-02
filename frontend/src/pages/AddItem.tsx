import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { BookmarkForm } from "@/components/bookmark/BookmarkForm";

export default function AddItem() {
  const navigate = useNavigate();

  return (
    <div className="animate-fade-in p-6 max-w-2xl mx-auto">
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 mb-6 p-2 -ml-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-all duration-200 cursor-pointer"
      >
        <ArrowLeft className="h-4 w-4" />
        Back
      </button>

      <div className="flex items-center justify-center min-h-[50vh]">
        <BookmarkForm onClose={() => navigate(-1)} />
      </div>
    </div>
  );
}
