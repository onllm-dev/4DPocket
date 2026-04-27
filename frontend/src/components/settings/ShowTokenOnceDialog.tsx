import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, Copy, X } from "lucide-react";
import type { CreateTokenResponse } from "@/hooks/use-api-tokens";
import { McpSetupPanel } from "./McpSetupPanel";
import { useFocusTrap } from "@/hooks/use-focus-trap";

export function ShowTokenOnceDialog({
  token,
  onClose,
}: {
  token: CreateTokenResponse;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, true);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [onClose]);

  async function copyToken() {
    try {
      await navigator.clipboard.writeText(token.token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable — user must copy manually
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-labelledby="show-token-dialog-title" ref={dialogRef}>
      <div className="w-full max-w-2xl rounded-xl bg-white dark:bg-gray-900 shadow-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-gray-100 dark:border-gray-800">
          <h3 id="show-token-dialog-title" className="text-base font-bold text-gray-900 dark:text-gray-100">
            Token created — copy it now
          </h3>
          <button onClick={onClose} aria-label="Close dialog" className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer">
            <X className="h-4 w-4 text-gray-500" />
          </button>
        </div>

        <div className="p-5 space-y-4 overflow-y-auto">
          <div className="flex items-start gap-2 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 p-3">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-amber-800 dark:text-amber-300">
              This is the only time this token will be shown. Treat it like a password — anyone with it has {token.role}-level access to your knowledge base.
              Store it in your MCP client's config, then close this dialog.
            </p>
          </div>

          <div>
            <div className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
              Token for <span className="font-semibold text-gray-900 dark:text-gray-100">{token.name}</span>
            </div>
            <div className="flex items-center gap-2">
              <code className="flex-1 px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 font-mono break-all">
                {token.token}
              </code>
              <button
                onClick={copyToken}
                className={`px-3 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors ${
                  copied
                    ? "bg-green-600 text-white"
                    : "bg-sky-600 text-white hover:bg-sky-700"
                }`}
              >
                {copied ? <><Check className="inline h-4 w-4 mr-1" /> Copied</> : <><Copy className="inline h-4 w-4 mr-1" /> Copy</>}
              </button>
            </div>
          </div>

          <McpSetupPanel token={token.token} />
        </div>

        <div className="flex items-center justify-end p-4 border-t border-gray-100 dark:border-gray-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-sky-600 text-white hover:bg-sky-700 transition-colors cursor-pointer"
          >
            I've saved my token
          </button>
        </div>
      </div>
    </div>
  );
}
