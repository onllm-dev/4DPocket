import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export function useKeyboardShortcuts() {
  const navigate = useNavigate();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input
      const target = e.target as HTMLElement;
      const tagName = target.tagName.toUpperCase();
      const type = target.getAttribute("type") || "";
      if (
        tagName === "INPUT" ||
        tagName === "TEXTAREA" ||
        tagName === "SELECT" ||
        target.isContentEditable ||
        (tagName === "INPUT" && (type === "search" || type === "email" || type === "text"))
      ) {
        return;
      }

      switch (e.key) {
        case "n":
          if (!e.metaKey && !e.ctrlKey) navigate("/add");
          break;
        case "/":
          e.preventDefault();
          window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
          break;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navigate]);
}
