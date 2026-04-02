import { Heart } from "lucide-react";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 py-4 px-6">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-gray-500 dark:text-gray-400">
        <span className="font-medium text-gray-600 dark:text-gray-300">
          4DPocket v0.1.0
        </span>
        <span className="flex items-center gap-1">
          Built with{" "}
          <Heart className="w-3 h-3 fill-red-500 text-red-500" /> by{" "}
          <a
            href="https://onllm.dev"
            className="text-sky-600 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300 transition-colors cursor-pointer"
            target="_blank"
            rel="noopener noreferrer"
          >
            onllm.dev
          </a>
        </span>
        <div className="flex items-center gap-1.5">
          <a
            href="https://onllm.dev"
            className="text-sky-600 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300 transition-colors cursor-pointer"
            target="_blank"
            rel="noopener noreferrer"
          >
            onllm.dev
          </a>
          <span className="text-gray-300 dark:text-gray-600">&middot;</span>
          <a
            href="https://github.com/onllm-dev/4DPocket"
            className="text-sky-600 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300 transition-colors cursor-pointer"
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub
          </a>
          <span className="text-gray-300 dark:text-gray-600">&middot;</span>
          <a
            href="https://buymeacoffee.com/prakersh"
            className="text-sky-600 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300 transition-colors cursor-pointer"
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
