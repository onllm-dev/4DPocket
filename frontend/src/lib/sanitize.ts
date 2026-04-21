import createDOMPurify from "dompurify";

// Use a private DOMPurify instance so our anchor-hardening hook does not
// leak onto, nor get clobbered by, any other DOMPurify consumer. The default
// `DOMPurify` export is a singleton bound to `window` — mutating its hook
// list globally is fragile because `removeHook(name)` only removes the most
// recently added hook for that name, so an unrelated consumer could silently
// displace ours (or have theirs displaced by ours). A local instance sidesteps
// the issue entirely and lets us register the hook permanently.
const purify = createDOMPurify(window);

// Force target=_blank + rel=noopener on all anchors (tabnabbing protection).
// Registered once at module load because it's idempotent and always desired
// for every HTML string we sanitize in this app.
purify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener noreferrer");
  }
});

// Shared allow-list used by content/section renderers. Kept in one place so
// renderers can't drift (e.g., one forgets to sanitize while the other does —
// which was the original defect we're fixing).
const ALLOWED_TAGS = [
  "h1", "h2", "h3", "h4", "h5", "h6",
  "p", "br", "hr",
  "strong", "em", "b", "i", "u", "s", "del", "ins",
  "a", "img",
  "ul", "ol", "li",
  "blockquote", "pre", "code",
  "table", "thead", "tbody", "tr", "th", "td",
  "div", "span", "figure", "figcaption",
  "mark", "sub", "sup", "abbr",
];

const ALLOWED_ATTR = [
  "href", "src", "alt", "title", "class", "id",
  "target", "rel", "width", "height",
];

export function sanitizeHtml(html: string): string {
  return purify.sanitize(html, { ALLOWED_TAGS, ALLOWED_ATTR });
}
