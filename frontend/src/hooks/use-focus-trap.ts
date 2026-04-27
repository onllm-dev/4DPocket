import { useEffect, type RefObject } from "react";

const FOCUSABLE_SELECTORS = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(", ");

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTORS)).filter(
    (el) => !el.closest("[hidden]") && el.tabIndex !== -1
  );
}

export function useFocusTrap(ref: RefObject<HTMLElement | null>, active: boolean): void {
  useEffect(() => {
    if (!active || !ref.current) return;

    const container = ref.current;
    const previouslyFocused = document.activeElement as HTMLElement | null;

    // Focus the first focusable element inside the container
    const focusables = getFocusableElements(container);
    if (focusables.length > 0) {
      focusables[0].focus();
    } else {
      // No focusable child; focus the container itself if possible
      if (container.tabIndex === -1) {
        container.setAttribute("tabindex", "-1");
      }
      container.focus();
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;

      const els = getFocusableElements(container);
      if (els.length === 0) {
        e.preventDefault();
        return;
      }

      const first = els[0];
      const last = els[els.length - 1];
      const active = document.activeElement;

      if (e.shiftKey) {
        if (active === first || active === container) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (active === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      // Restore focus to the element that had it before the trap was active
      if (previouslyFocused && typeof previouslyFocused.focus === "function") {
        previouslyFocused.focus();
      }
    };
  }, [active, ref]);
}
