import { useState, useCallback, useEffect, useRef } from "react";
import { Highlighter, X } from "lucide-react";
import { api } from "@/api/client";
import { useQueryClient } from "@tanstack/react-query";
import type { Highlight } from "@/hooks/use-highlights";

interface TextHighlighterProps {
  itemId?: string;
  noteId?: string;
  highlights?: Highlight[];
  children: React.ReactNode;
}

const COLORS = [
  { name: "yellow", bg: "bg-yellow-200 dark:bg-yellow-700/50", ring: "ring-yellow-400" },
  { name: "green", bg: "bg-green-200 dark:bg-green-700/50", ring: "ring-green-400" },
  { name: "blue", bg: "bg-blue-200 dark:bg-blue-700/50", ring: "ring-blue-400" },
  { name: "red", bg: "bg-red-200 dark:bg-red-700/50", ring: "ring-red-400" },
  { name: "purple", bg: "bg-purple-200 dark:bg-purple-700/50", ring: "ring-purple-400" },
];

const COLOR_MARK_CLASSES: Record<string, string> = {
  yellow: "bg-yellow-200 dark:bg-yellow-700/50",
  green: "bg-green-200 dark:bg-green-700/50",
  blue: "bg-blue-200 dark:bg-blue-700/50",
  red: "bg-red-200 dark:bg-red-700/50",
  purple: "bg-purple-200 dark:bg-purple-700/50",
};

function applyHighlightsToDOM(container: HTMLElement, highlights: Highlight[]) {
  if (!highlights.length) return;

  // Remove previously applied highlight marks
  container.querySelectorAll("mark[data-highlight-id]").forEach((mark) => {
    const parent = mark.parentNode;
    if (!parent) return;
    while (mark.firstChild) {
      parent.insertBefore(mark.firstChild, mark);
    }
    parent.removeChild(mark);
    parent.normalize();
  });

  // Apply each highlight by searching for matching text in text nodes
  for (const hl of highlights) {
    if (!hl.text) continue;
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    let node: Text | null;

    while ((node = walker.nextNode() as Text | null)) {
      const idx = node.nodeValue?.indexOf(hl.text) ?? -1;
      if (idx === -1) continue;

      // Already inside a highlight mark? skip
      if (node.parentElement?.closest("mark[data-highlight-id]")) continue;

      const range = document.createRange();
      range.setStart(node, idx);
      range.setEnd(node, idx + hl.text.length);

      const mark = document.createElement("mark");
      mark.setAttribute("data-highlight-id", hl.id);
      mark.className = `rounded px-0.5 ${COLOR_MARK_CLASSES[hl.color] ?? COLOR_MARK_CLASSES.yellow}`;
      range.surroundContents(mark);

      // Only highlight first occurrence per highlight
      break;
    }
  }
}

export default function TextHighlighter({ itemId, noteId, highlights = [], children }: TextHighlighterProps) {
  const [showPicker, setShowPicker] = useState(false);
  const [pickerPos, setPickerPos] = useState({ x: 0, y: 0 });
  const [selectedText, setSelectedText] = useState("");
  const [selectedPosition, setSelectedPosition] = useState<{ start: number; end: number } | null>(null);
  const [saving, setSaving] = useState(false);
  const qc = useQueryClient();
  const containerRef = useRef<HTMLDivElement>(null);

  // Apply highlight overlays after render
  useEffect(() => {
    if (!containerRef.current || !highlights.length) return;
    // Small delay to ensure children have rendered
    const timer = setTimeout(() => {
      if (containerRef.current) {
        applyHighlightsToDOM(containerRef.current, highlights);
      }
    }, 100);
    return () => clearTimeout(timer);
  }, [highlights]);

  const handleTextSelect = useCallback(
    (text: string, position: { start: number; end: number }) => {
      if (!text.trim()) {
        setShowPicker(false);
        return;
      }
      setSelectedText(text);
      setSelectedPosition(position);

      const selection = window.getSelection();
      if (selection && selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        setPickerPos({
          x: rect.left + rect.width / 2,
          y: rect.top - 10,
        });
      }
      setShowPicker(true);
    },
    []
  );

  const handleColorPick = async (color: string) => {
    if (!selectedText || !selectedPosition) return;

    setSaving(true);
    try {
      await api.post("/api/v1/highlights", {
        ...(itemId ? { item_id: itemId } : { note_id: noteId }),
        text: selectedText,
        color,
        position: selectedPosition,
      });

      qc.invalidateQueries({ queryKey: ["highlights"] });
      window.getSelection()?.removeAllRanges();
    } catch {
    } finally {
      setSaving(false);
      setShowPicker(false);
      setSelectedText("");
      setSelectedPosition(null);
    }
  };

  const handleDismiss = () => {
    setShowPicker(false);
    setSelectedText("");
    setSelectedPosition(null);
  };

  return (
    <div className="relative">
      <div
        ref={containerRef}
        onMouseUp={() => {
          const selection = window.getSelection();
          if (!selection || selection.isCollapsed) {
            setShowPicker(false);
            return;
          }
          const text = selection.toString().trim();
          if (!text) return;

          const range = selection.getRangeAt(0);
          const container = range.commonAncestorContainer.parentElement?.closest("[data-content-area]");
          if (!container) return;

          const preRange = document.createRange();
          preRange.selectNodeContents(container);
          preRange.setEnd(range.startContainer, range.startOffset);
          const start = preRange.toString().length;

          handleTextSelect(text, { start, end: start + text.length });
        }}
        data-content-area
      >
        {children}
      </div>

      {showPicker && (
        <div
          className="fixed z-50 flex items-center gap-1 px-2 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg"
          style={{
            left: `${pickerPos.x}px`,
            top: `${pickerPos.y}px`,
            transform: "translate(-50%, -100%)",
          }}
        >
          <Highlighter className="w-3.5 h-3.5 text-gray-400 mr-1" />
          {COLORS.map((c) => (
            <button
              key={c.name}
              onClick={() => handleColorPick(c.name)}
              disabled={saving}
              className={`w-6 h-6 rounded-full ${c.bg} hover:ring-2 ${c.ring} transition-all ${
                saving ? "opacity-50" : ""
              }`}
              title={c.name}
            />
          ))}
          <button
            onClick={handleDismiss}
            className="ml-1 p-0.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
