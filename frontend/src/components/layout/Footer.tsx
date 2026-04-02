import { Heart } from "lucide-react";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-sky-100 dark:border-gray-800 bg-white dark:bg-gray-950 py-4 px-6">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-gray-500 dark:text-gray-400">
        <span className="flex items-center gap-1.5 font-medium text-gray-600 dark:text-gray-300">
          <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none">
            <circle cx="12" cy="12" r="10" fill="#0096C7"/>
            <circle cx="12" cy="13" r="6" fill="white"/>
            <circle cx="12" cy="9" r="1.5" fill="#EF4444"/>
            <circle cx="12" cy="16" r="2" fill="#FCD34D" stroke="#D97706" strokeWidth="0.75"/>
          </svg>
          4DPocket v0.1.0
        </span>
        <span className="italic text-gray-400 dark:text-gray-500 hidden sm:block">
          Reach into your pocket - anything's possible.
        </span>
        <span className="flex items-center gap-1">
          Built with{" "}
          <Heart className="w-3 h-3 fill-red-500 text-red-500" /> by{" "}
          <a
            href="https://onllm.dev"
            className="text-[#0096C7] hover:text-[#0077A8] dark:text-sky-400 dark:hover:text-sky-300 transition-colors cursor-pointer"
            target="_blank"
            rel="noopener noreferrer"
          >
            onllm.dev
          </a>
        </span>
        <div className="flex items-center gap-1.5">
          <a
            href="https://onllm.dev"
            className="text-[#0096C7] hover:text-[#0077A8] dark:text-sky-400 dark:hover:text-sky-300 transition-colors cursor-pointer"
            target="_blank"
            rel="noopener noreferrer"
          >
            onllm.dev
          </a>
          <span className="text-gray-300 dark:text-gray-600">&middot;</span>
          <a
            href="https://github.com/onllm-dev/4DPocket"
            className="text-[#0096C7] hover:text-[#0077A8] dark:text-sky-400 dark:hover:text-sky-300 transition-colors cursor-pointer"
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub
          </a>
          <span className="text-gray-300 dark:text-gray-600">&middot;</span>
          <a
            href="https://buymeacoffee.com/prakersh"
            className="text-[#0096C7] hover:text-[#0077A8] dark:text-sky-400 dark:hover:text-sky-300 transition-colors cursor-pointer"
            target="_blank"
            rel="noopener noreferrer"
            title="Support 4DPocket"
          >
            Support 4DPocket
          </a>
        </div>
      </div>
    </footer>
  );
}
