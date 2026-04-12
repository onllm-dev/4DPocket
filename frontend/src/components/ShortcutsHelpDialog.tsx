import { useEffect, useState } from "react";
import { Keyboard, X } from "lucide-react";

const SHORTCUTS: { keys: string[]; label: string }[] = [
  { keys: ["Cmd/Ctrl", "K"], label: "Open command palette" },
  { keys: ["/"], label: "Focus search" },
  { keys: ["n"], label: "Save new item" },
  { keys: ["?"], label: "Show this help" },
  { keys: ["Esc"], label: "Close dialog / cancel" },
];

export function ShortcutsHelpDialog() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handleOpen = () => setOpen(true);
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("4dp:open-shortcuts", handleOpen as EventListener);
    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("4dp:open-shortcuts", handleOpen as EventListener);
      window.removeEventListener("keydown", handleKey);
    };
  }, []);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-md rounded-2xl bg-white dark:bg-gray-900 shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-5 border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2">
            <Keyboard className="h-4 w-4 text-sky-600" />
            <h3 className="text-base font-bold text-gray-900 dark:text-gray-100">
              Keyboard shortcuts
            </h3>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer"
            aria-label="Close"
          >
            <X className="h-4 w-4 text-gray-500" />
          </button>
        </div>
        <ul className="p-5 space-y-3">
          {SHORTCUTS.map((s) => (
            <li key={s.label} className="flex items-center justify-between text-sm">
              <span className="text-gray-700 dark:text-gray-300">{s.label}</span>
              <span className="flex items-center gap-1">
                {s.keys.map((k) => (
                  <kbd
                    key={k}
                    className="px-2 py-0.5 text-xs font-mono rounded border border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 shadow-[inset_0_-1px_0_rgba(0,0,0,0.08)]"
                  >
                    {k}
                  </kbd>
                ))}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
