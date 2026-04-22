export default defineContentScript({
  matches: ["<all_urls>"],
  runAt: "document_idle",

  main() {
    let tooltipContainer: HTMLElement | null = null;

    // --- Helpers ---

    function getCssSelector(el: Element): string {
      const parts: string[] = [];
      let current: Element | null = el;
      while (current && current !== document.body) {
        let selector = current.tagName.toLowerCase();
        if (current.id) {
          selector += `#${current.id}`;
          parts.unshift(selector);
          break;
        }
        const parent = current.parentElement;
        if (parent) {
          const siblings = Array.from(parent.children).filter(
            (c) => c.tagName === current!.tagName
          );
          if (siblings.length > 1) {
            const index = siblings.indexOf(current) + 1;
            selector += `:nth-of-type(${index})`;
          }
        }
        parts.unshift(selector);
        current = current.parentElement;
      }
      return parts.join(" > ");
    }

    function getSelectionContext(selection: Selection): string {
      const range = selection.getRangeAt(0);
      const container = range.commonAncestorContainer;
      const parentEl =
        container.nodeType === Node.TEXT_NODE
          ? container.parentElement
          : (container as Element);
      return (parentEl?.textContent || "").slice(0, 500);
    }

    function removeTooltip() {
      if (tooltipContainer) {
        tooltipContainer.remove();
        tooltipContainer = null;
      }
    }

    function createTooltip(x: number, y: number, onSave: () => void) {
      removeTooltip();

      const container = document.createElement("div");
      container.id = "fdp-highlight-tooltip";
      // Position container off-screen initially; shadow DOM content handles visual placement
      container.style.cssText =
        "position:fixed;top:0;left:0;width:0;height:0;z-index:2147483647;pointer-events:none;";

      const shadow = container.attachShadow({ mode: "closed" });

      const style = document.createElement("style");
      style.textContent = `
        .tooltip {
          position: fixed;
          z-index: 2147483647;
          pointer-events: auto;
          display: flex;
          flex-direction: column;
          align-items: center;
          filter: drop-shadow(0 4px 12px rgba(0,0,0,0.25));
          animation: fdp-fade-in 0.15s ease-out;
        }
        @keyframes fdp-fade-in {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .arrow {
          width: 0;
          height: 0;
          border-left: 6px solid transparent;
          border-right: 6px solid transparent;
          border-bottom: 6px solid #0096C7;
        }
        .btn {
          background: #0096C7;
          color: #fff;
          border: none;
          padding: 6px 14px;
          border-radius: 6px;
          font: 600 13px/1 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          cursor: pointer;
          white-space: nowrap;
          transition: background 0.15s;
        }
        .btn:hover {
          background: #0077A8;
        }
        .btn.success {
          background: #16a34a;
          pointer-events: none;
        }
        .btn.error {
          background: #dc2626;
          pointer-events: none;
        }
      `;
      shadow.appendChild(style);

      const tooltip = document.createElement("div");
      tooltip.className = "tooltip";
      tooltip.style.left = `${x}px`;
      tooltip.style.top = `${y}px`;

      const arrow = document.createElement("div");
      arrow.className = "arrow";

      const btn = document.createElement("button");
      btn.className = "btn";
      btn.textContent = "Save to 4DPocket";
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        e.preventDefault();
        onSave();
      });

      tooltip.appendChild(arrow);
      tooltip.appendChild(btn);
      shadow.appendChild(tooltip);
      document.body.appendChild(container);

      // Clamp to viewport
      requestAnimationFrame(() => {
        const rect = btn.getBoundingClientRect();
        const vw = window.innerWidth;
        let adjustedX = x;
        if (adjustedX + rect.width / 2 > vw - 8) {
          adjustedX = vw - rect.width / 2 - 8;
        }
        if (adjustedX - rect.width / 2 < 8) {
          adjustedX = rect.width / 2 + 8;
        }
        tooltip.style.left = `${adjustedX}px`;
      });

      tooltipContainer = container;

      return { tooltip, btn, shadow };
    }

    function showResult(
      btn: HTMLButtonElement,
      success: boolean
    ) {
      btn.textContent = success ? "\u2713 Saved" : "\u2717 Failed";
      btn.className = success ? "btn success" : "btn error";
      setTimeout(removeTooltip, 1500);
    }

    // --- Event listeners ---

    document.addEventListener("mouseup", (e) => {
      // Small delay so the selection is finalized
      setTimeout(() => {
        const selection = window.getSelection();
        if (!selection || selection.isCollapsed) return;

        const text = selection.toString().trim();
        if (!text) return;

        // Don't show tooltip if click was inside our own tooltip
        if (
          tooltipContainer &&
          (e.target as Node)?.getRootNode?.() === tooltipContainer
        ) {
          return;
        }

        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();

        // Position above the selection, centered
        const x = rect.left + rect.width / 2;
        const y = rect.top - 10;

        const anchorNode = selection.anchorNode;
        const anchorEl =
          anchorNode?.nodeType === Node.TEXT_NODE
            ? anchorNode.parentElement
            : (anchorNode as Element);

        const { btn } = createTooltip(x, y, () => {
          // Capture data before selection might clear
          const selText = text;
          const context = getSelectionContext(selection);
          const selector = anchorEl ? getCssSelector(anchorEl) : "";
          const offset = selection.anchorOffset;

          btn.textContent = "Saving...";
          btn.style.pointerEvents = "none";

          chrome.runtime.sendMessage(
            {
              type: "SAVE_HIGHLIGHT",
              data: {
                url: window.location.href,
                title: document.title,
                text: selText,
                context,
                position: {
                  selector,
                  textOffset: offset,
                  textLength: selText.length,
                },
              },
            },
            (response) => {
              if (chrome.runtime.lastError) {
                showResult(btn, false);
                return;
              }
              if (!response || typeof response !== "object" || !("status" in response)) {
                console.warn("[4dp] unexpected response", response);
                showResult(btn, false);
                return;
              }
              showResult(btn, response.status === "success");
            }
          );
        });
      }, 10);
    });

    document.addEventListener("mousedown", (e) => {
      if (!tooltipContainer) return;
      // Check if click is inside the shadow DOM tooltip
      const path = e.composedPath();
      if (path.includes(tooltipContainer)) return;
      removeTooltip();
    });

    // Also remove on scroll (selection likely changed)
    document.addEventListener("scroll", removeTooltip, { passive: true });
  },
});
