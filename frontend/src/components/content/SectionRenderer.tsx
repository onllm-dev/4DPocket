import { useMemo, useState } from "react";
import {
  ArrowUp,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Hash,
  Quote as QuoteIcon,
  User,
} from "lucide-react";

// Matches the backend dataclass in processors/sections.py (camelCase→snake_case).
export interface Section {
  id: string;
  kind: string;
  order: number;
  parent_id?: string | null;
  depth?: number;
  text: string;
  raw_html?: string | null;
  role?: string;
  source_url?: string | null;
  char_start?: number | null;
  char_end?: number | null;
  page_no?: number | null;
  timestamp_start_s?: number | null;
  timestamp_end_s?: number | null;
  author?: string | null;
  author_id?: string | null;
  score?: number | null;
  upvotes?: number | null;
  is_accepted?: boolean;
  created_at?: string | null;
  extra?: Record<string, unknown>;
}

// ─── helpers ─────────────────────────────────────────────────────

function formatTimestamp(seconds?: number | null): string {
  if (seconds == null || !Number.isFinite(seconds)) return "";
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    : `${m}:${String(s).padStart(2, "0")}`;
}

function formatScore(n?: number | null): string {
  if (n == null || !Number.isFinite(n)) return "";
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function looksLikeVideo(sections: Section[]): boolean {
  return sections.some(
    (s) => s.kind === "transcript_segment" || s.kind === "chapter",
  );
}

function looksLikeForum(sections: Section[]): boolean {
  return sections.some((s) => s.kind === "post" || s.kind === "comment" || s.kind === "reply");
}

function looksLikeQA(sections: Section[]): boolean {
  return sections.some(
    (s) => s.kind === "question" || s.kind === "accepted_answer" || s.kind === "answer",
  );
}

function looksLikePaged(sections: Section[]): boolean {
  return sections.some((s) => s.kind === "page" && s.page_no != null);
}

// ─── primitives ──────────────────────────────────────────────────

function ParagraphBlock({ text }: { text: string }) {
  return (
    <p className="text-[15px] leading-relaxed text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
      {text}
    </p>
  );
}

function HeadingBlock({ text, depth = 0 }: { text: string; depth?: number }) {
  const level = Math.max(1, Math.min(6, (depth ?? 0) + 1));
  const cls =
    level === 1 ? "text-2xl font-bold mt-6"
    : level === 2 ? "text-xl font-semibold mt-5"
    : level === 3 ? "text-lg font-semibold mt-4"
    : "text-base font-semibold mt-3";
  return <div className={`${cls} text-gray-900 dark:text-gray-100`}>{text}</div>;
}

function QuoteBlock({ text }: { text: string }) {
  return (
    <blockquote className="border-l-4 border-sky-300 dark:border-sky-700 bg-sky-50/50 dark:bg-sky-900/10 pl-4 py-2 italic text-gray-700 dark:text-gray-300">
      <QuoteIcon className="inline w-3 h-3 mr-1 opacity-50" />
      {text}
    </blockquote>
  );
}

function CodeBlock({ text, language }: { text: string; language?: string }) {
  return (
    <pre className="rounded-lg bg-gray-900 dark:bg-black text-gray-100 text-xs overflow-x-auto p-4 whitespace-pre">
      {language && (
        <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-2">
          {language}
        </div>
      )}
      <code>{text}</code>
    </pre>
  );
}

function ListItemBlock({ text }: { text: string }) {
  return (
    <li className="ml-5 list-disc text-gray-800 dark:text-gray-200 leading-relaxed">
      {text}
    </li>
  );
}

function AuthorLine({
  author,
  score,
  createdAt,
  accepted,
}: {
  author?: string | null;
  score?: number | null;
  createdAt?: string | null;
  accepted?: boolean;
}) {
  if (!author && score == null && !createdAt && !accepted) return null;
  return (
    <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mb-1.5">
      {author && (
        <span className="inline-flex items-center gap-1 font-medium">
          <User className="w-3 h-3" />
          {author.startsWith("@") ? author : `@${author}`}
        </span>
      )}
      {score != null && (
        <span className="inline-flex items-center gap-0.5">
          <ArrowUp className="w-3 h-3" />
          {formatScore(score)}
        </span>
      )}
      {accepted && (
        <span className="inline-flex items-center gap-0.5 text-green-600 dark:text-green-400 font-medium">
          <CheckCircle2 className="w-3 h-3" />
          Accepted
        </span>
      )}
      {createdAt && <span className="text-gray-400 dark:text-gray-600">·</span>}
      {createdAt && <span>{createdAt.slice(0, 10)}</span>}
    </div>
  );
}

// ─── view variants ───────────────────────────────────────────────

function ForumView({ sections }: { sections: Section[] }) {
  const [collapsedParents, setCollapsedParents] = useState<Set<string>>(new Set());
  const toggle = (id: string) => {
    setCollapsedParents((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Walk in order; comments/replies are parented so we can indent by depth.
  return (
    <div className="space-y-4">
      {sections.map((s) => {
        if (s.kind === "post") {
          return (
            <div
              key={s.id}
              className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5"
            >
              <AuthorLine
                author={s.author}
                score={s.score}
                createdAt={s.created_at}
              />
              <ParagraphBlock text={s.text} />
              {s.extra && Boolean(s.extra.subreddit) && (
                <div className="mt-2 inline-flex items-center gap-1 px-2 py-0.5 rounded bg-orange-50 dark:bg-orange-900/20 text-orange-600 text-[11px]">
                  <Hash className="w-3 h-3" />r/{String(s.extra.subreddit)}
                </div>
              )}
            </div>
          );
        }
        if (s.kind === "comment" || s.kind === "reply" || s.kind === "quoted_post") {
          const depth = Math.max(0, Math.min(5, s.depth ?? 1));
          const indentPx = depth * 16;
          const isQuoted = s.kind === "quoted_post";
          const collapsed = collapsedParents.has(s.id);
          return (
            <div
              key={s.id}
              style={{ marginLeft: `${indentPx}px` }}
              className={`rounded-lg border-l-2 ${
                isQuoted
                  ? "border-indigo-300 bg-indigo-50/40 dark:border-indigo-700 dark:bg-indigo-900/10"
                  : "border-sky-200 bg-sky-50/40 dark:border-sky-800 dark:bg-sky-900/10"
              } pl-3 pr-3 py-2.5`}
            >
              <div className="flex items-start gap-2">
                <button
                  onClick={() => toggle(s.id)}
                  className="mt-0.5 p-0.5 rounded hover:bg-gray-200/50 dark:hover:bg-gray-700/50"
                  aria-label={collapsed ? "Expand" : "Collapse"}
                >
                  {collapsed ? (
                    <ChevronRight className="w-3 h-3 text-gray-500" />
                  ) : (
                    <ChevronDown className="w-3 h-3 text-gray-500" />
                  )}
                </button>
                <div className="flex-1 min-w-0">
                  <AuthorLine
                    author={s.author}
                    score={s.score}
                    createdAt={s.created_at}
                  />
                  {!collapsed && (
                    <p className="text-[14px] leading-relaxed text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                      {s.text}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}

function QAView({ sections }: { sections: Section[] }) {
  return (
    <div className="space-y-5">
      {sections.map((s) => {
        if (s.kind === "question") {
          return (
            <div
              key={s.id}
              className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5"
            >
              <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
                Question
              </div>
              <AuthorLine author={s.author} score={s.score} createdAt={s.created_at} />
              {s.raw_html ? (
                <div
                  className="prose prose-sm dark:prose-invert max-w-none"
                  dangerouslySetInnerHTML={{ __html: s.raw_html }}
                />
              ) : (
                <ParagraphBlock text={s.text} />
              )}
            </div>
          );
        }
        if (s.kind === "accepted_answer" || s.kind === "answer") {
          const accepted = s.kind === "accepted_answer" || s.is_accepted;
          return (
            <div
              key={s.id}
              className={`rounded-xl border p-5 ${
                accepted
                  ? "border-green-400 dark:border-green-700 bg-green-50/40 dark:bg-green-900/10"
                  : "border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900"
              }`}
            >
              <div className="text-xs font-semibold uppercase tracking-wider mb-2 text-gray-500">
                {accepted ? (
                  <span className="text-green-600 dark:text-green-400 inline-flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Accepted Answer
                  </span>
                ) : (
                  "Answer"
                )}
              </div>
              <AuthorLine
                author={s.author}
                score={s.score}
                createdAt={s.created_at}
                accepted={accepted}
              />
              {s.raw_html ? (
                <div
                  className="prose prose-sm dark:prose-invert max-w-none"
                  dangerouslySetInnerHTML={{ __html: s.raw_html }}
                />
              ) : (
                <ParagraphBlock text={s.text} />
              )}
            </div>
          );
        }
        if (s.kind === "comment") {
          return (
            <div
              key={s.id}
              className="ml-4 border-l-2 border-gray-200 dark:border-gray-800 pl-3 py-1 text-sm text-gray-600 dark:text-gray-400"
            >
              <AuthorLine author={s.author} score={s.score} createdAt={s.created_at} />
              <span>{s.text}</span>
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}

function VideoView({ sections }: { sections: Section[] }) {
  // Group transcript segments under their chapter; chapters without
  // transcript children still render as an anchor.
  const grouped = useMemo(() => {
    const out: { chapter: Section | null; segments: Section[] }[] = [];
    let current: { chapter: Section | null; segments: Section[] } | null = null;
    for (const s of sections) {
      if (s.kind === "chapter") {
        current = { chapter: s, segments: [] };
        out.push(current);
      } else if (s.kind === "transcript_segment") {
        if (!current) {
          current = { chapter: null, segments: [] };
          out.push(current);
        }
        current.segments.push(s);
      }
    }
    return out;
  }, [sections]);

  const description = sections.find(
    (s) => s.kind === "paragraph" && s.role === "supplemental",
  );

  return (
    <div className="space-y-6">
      {description && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
            Description
          </div>
          <ParagraphBlock text={description.text} />
        </div>
      )}
      {grouped.length === 0 && (
        <div className="text-sm text-gray-500 italic">
          No transcript available.
        </div>
      )}
      {grouped.map((g, i) => (
        <div key={g.chapter?.id ?? `group-${i}`}>
          {g.chapter && (
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300 text-xs font-medium">
                {formatTimestamp(g.chapter.timestamp_start_s)}
              </span>
              <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
                {g.chapter.text}
              </h3>
            </div>
          )}
          <div className="space-y-2">
            {g.segments.map((seg) => (
              <div
                key={seg.id}
                className="flex gap-3 text-sm leading-relaxed"
              >
                <span className="flex-shrink-0 w-16 text-[11px] font-mono text-gray-500 dark:text-gray-500 pt-0.5">
                  {formatTimestamp(seg.timestamp_start_s)}
                </span>
                <span className="text-gray-800 dark:text-gray-200 flex-1">
                  {seg.text}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function PagedView({ sections }: { sections: Section[] }) {
  // Group body sections under their page anchor.
  const groups = useMemo(() => {
    const out: { pageNo: number | null; items: Section[] }[] = [];
    let current: { pageNo: number | null; items: Section[] } | null = null;
    for (const s of sections) {
      if (s.kind === "page") {
        current = { pageNo: s.page_no ?? null, items: [] };
        out.push(current);
      } else if (current) {
        current.items.push(s);
      } else {
        current = { pageNo: s.page_no ?? null, items: [s] };
        out.push(current);
      }
    }
    return out;
  }, [sections]);

  return (
    <div className="space-y-6">
      {groups.map((g, i) => (
        <div key={`pg-${g.pageNo ?? i}`} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
          {g.pageNo != null && (
            <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3 pb-2 border-b border-gray-100 dark:border-gray-800">
              Page {g.pageNo}
            </div>
          )}
          <div className="space-y-3">
            {g.items.map((s) => {
              if (s.kind === "heading") return <HeadingBlock key={s.id} text={s.text} depth={s.depth} />;
              if (s.kind === "paragraph") return <ParagraphBlock key={s.id} text={s.text} />;
              if (s.kind === "quote") return <QuoteBlock key={s.id} text={s.text} />;
              if (s.kind === "list_item") return <ListItemBlock key={s.id} text={s.text} />;
              if (s.kind === "code") {
                const lang = typeof s.extra?.language === "string" ? s.extra.language : undefined;
                return <CodeBlock key={s.id} text={s.text} language={lang} />;
              }
              return null;
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function ArticleView({ sections }: { sections: Section[] }) {
  return (
    <div className="space-y-3 prose-spacing">
      {sections.map((s) => {
        if (s.kind === "title") return null; // page already renders title
        if (s.kind === "subtitle") {
          return (
            <p
              key={s.id}
              className="text-lg text-gray-600 dark:text-gray-400 italic font-medium"
            >
              {s.text}
            </p>
          );
        }
        if (s.kind === "heading") return <HeadingBlock key={s.id} text={s.text} depth={s.depth} />;
        if (s.kind === "paragraph") return <ParagraphBlock key={s.id} text={s.text} />;
        if (s.kind === "quote") return <QuoteBlock key={s.id} text={s.text} />;
        if (s.kind === "list_item") return <ListItemBlock key={s.id} text={s.text} />;
        if (s.kind === "code") {
          const lang = typeof s.extra?.language === "string" ? s.extra.language : undefined;
          return <CodeBlock key={s.id} text={s.text} language={lang} />;
        }
        if (s.kind === "visual_caption" || s.kind === "ocr_text") {
          return (
            <div
              key={s.id}
              className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-sm text-gray-700 dark:text-gray-300"
            >
              <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
                {s.kind === "visual_caption" ? "Image description" : "OCR text"}
              </div>
              {s.text}
            </div>
          );
        }
        if (s.kind === "metadata_block") {
          return (
            <div
              key={s.id}
              className="rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 px-3 py-2 text-xs text-amber-800 dark:text-amber-300"
            >
              {s.text}
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}

// ─── public entry ────────────────────────────────────────────────

export function SectionRenderer({ sections }: { sections: Section[] }) {
  const nonEmpty = sections.filter((s) => (s.text || "").trim().length > 0);
  if (nonEmpty.length === 0) return null;

  if (looksLikeForum(nonEmpty)) return <ForumView sections={nonEmpty} />;
  if (looksLikeQA(nonEmpty)) return <QAView sections={nonEmpty} />;
  if (looksLikeVideo(nonEmpty)) return <VideoView sections={nonEmpty} />;
  if (looksLikePaged(nonEmpty)) return <PagedView sections={nonEmpty} />;
  return <ArticleView sections={nonEmpty} />;
}
