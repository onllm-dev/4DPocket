import { Heart } from "lucide-react";

export function Footer() {
  return (
    <footer className="hidden md:block mt-auto border-t border-sky-100 dark:border-gray-800 bg-white dark:bg-gray-950 py-2.5 px-6">
      <div className="max-w-7xl mx-auto flex items-center justify-between text-[11px] text-gray-400 dark:text-gray-500">
        <span className="flex items-center gap-1.5">
          <svg viewBox="0 0 24 24" className="w-3.5 h-3.5" fill="none">
            <circle cx="12" cy="12" r="10" fill="#0096C7"/>
            <circle cx="12" cy="13" r="6" fill="white"/>
            <circle cx="12" cy="9" r="1.5" fill="#EF4444"/>
            <circle cx="12" cy="16" r="2" fill="#FCD34D" stroke="#D97706" strokeWidth="0.75"/>
          </svg>
          4DPocket v0.1.0
        </span>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            Built with <Heart className="w-2.5 h-2.5 fill-red-500 text-red-500" /> by{" "}
            <a href="https://onllm.dev" className="text-[#0096C7] hover:text-[#0077A8] dark:text-sky-400 transition-colors cursor-pointer" target="_blank" rel="noopener noreferrer">onllm.dev</a>
          </span>
          <span className="text-gray-300 dark:text-gray-700">&middot;</span>
          <a href="https://github.com/onllm-dev/4DPocket" className="text-[#0096C7] hover:text-[#0077A8] dark:text-sky-400 transition-colors cursor-pointer" target="_blank" rel="noopener noreferrer">GitHub</a>
          <span className="text-gray-300 dark:text-gray-700">&middot;</span>
          <a href="https://buymeacoffee.com/prakersh" className="text-[#0096C7] hover:text-[#0077A8] dark:text-sky-400 transition-colors cursor-pointer" target="_blank" rel="noopener noreferrer">Support</a>
        </div>
      </div>
    </footer>
  );
}
