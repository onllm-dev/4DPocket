import { useState, useRef, useMemo } from "react";
import { marked } from "marked";
import { ExternalLink, Copy, Code, FileText, Check } from "lucide-react";
import { sanitizeHtml } from "../../lib/sanitize";

interface ContentRendererProps {
  content: string | null;
  rawContent?: string | null;
  sourceUrl?: string | null;
  sourcePlatform?: string | null;
  onTextSelect?: (text: string, position: { start: number; end: number }) => void;
}

// Platforms that output markdown content from their processors
const MARKDOWN_PLATFORMS = new Set([
  "reddit", "github", "stackoverflow", "youtube",
  "hackernews", "medium", "substack",
]);

function isLikelyMarkdown(text: string): boolean {
  // Detect markdown patterns: headers, bold, links, code blocks
  return /^#{1,6}\s/m.test(text) ||
    /\*\*[^*]+\*\*/m.test(text) ||
    /```[\s\S]*?```/m.test(text) ||
    /^\s*[-*]\s/m.test(text);
}

function extractDomain(url: string): string {
  try {
    return new URL(url).hostname.replace("www.", "");
  } catch {
    return url;
  }
}

export default function ContentRenderer({
  content,
  rawContent,
  sourceUrl,
  sourcePlatform,
  onTextSelect,
}: ContentRendererProps) {
  const [viewMode, setViewMode] = useState<"rendered" | "raw">("rendered");
  const [copied, setCopied] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const displayContent = content || rawContent || "";

  // Convert markdown to HTML for platforms that output markdown
  const htmlContent = useMemo(() => {
    const platform = sourcePlatform?.replace(/^SourcePlatform\./, "") || "";
    if (MARKDOWN_PLATFORMS.has(platform) || isLikelyMarkdown(displayContent)) {
      return marked.parse(displayContent, { async: false }) as string;
    }
    return displayContent;
  }, [displayContent, sourcePlatform]);

  const sanitizedHtml = useMemo(() => sanitizeHtml(htmlContent), [htmlContent]);

  const handleCopy = async () => {
    const text = rawContent || content || "";
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleMouseUp = () => {
    if (!onTextSelect || !contentRef.current) return;
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;

    const text = selection.toString().trim();
    if (!text) return;

    const range = selection.getRangeAt(0);
    const preRange = document.createRange();
    preRange.selectNodeContents(contentRef.current);
    preRange.setEnd(range.startContainer, range.startOffset);
    const start = preRange.toString().length;

    onTextSelect(text, { start, end: start + text.length });
  };

  if (!displayContent) return null;

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-gray-800/50">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2">
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs text-sky-600 dark:text-sky-400 hover:underline"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              {extractDomain(sourceUrl)}
            </a>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400 transition-colors"
            title="Copy content"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
          <div className="flex bg-gray-200 dark:bg-gray-700 rounded p-0.5">
            <button
              onClick={() => setViewMode("rendered")}
              className={`inline-flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors ${
                viewMode === "rendered"
                  ? "bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm"
                  : "text-gray-500 dark:text-gray-400"
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              Reader
            </button>
            <button
              onClick={() => setViewMode("raw")}
              className={`inline-flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors ${
                viewMode === "raw"
                  ? "bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm"
                  : "text-gray-500 dark:text-gray-400"
              }`}
            >
              <Code className="w-3.5 h-3.5" />
              Raw
            </button>
          </div>
        </div>
      </div>

      {/* Content area */}
      <div className="p-6">
        {viewMode === "rendered" ? (
          <div
            ref={contentRef}
            onMouseUp={handleMouseUp}
            className="prose dark:prose-invert max-w-none text-sm leading-relaxed
              prose-headings:text-gray-900 dark:prose-headings:text-gray-100
              prose-a:text-sky-600 dark:prose-a:text-sky-400
              prose-img:rounded-lg prose-img:max-h-96
              prose-code:bg-gray-100 dark:prose-code:bg-gray-700 prose-code:px-1 prose-code:rounded
              prose-blockquote:border-sky-300 dark:prose-blockquote:border-sky-600"
            dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
          />
        ) : (
          <pre className="text-xs font-mono text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words overflow-x-auto bg-gray-50 dark:bg-gray-900 p-4 rounded-lg">
            {rawContent || content}
          </pre>
        )}
      </div>
    </div>
  );
}
