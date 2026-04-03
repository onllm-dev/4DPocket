import { Outlet } from "react-router-dom";
import { BottomNav } from "./BottomNav";
import { Footer } from "./Footer";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { CommandPalette } from "@/components/common/CommandPalette";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { useKeyboardShortcuts } from "@/hooks/use-keyboard";

export function AppShell() {
  useKeyboardShortcuts();

  return (
    <div className="flex h-screen bg-sky-50/30 dark:bg-[#0C1222] text-gray-900 dark:text-gray-100">
      <a href="#main-content" className="skip-to-content focus-ring">
        Skip to content
      </a>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main
          id="main-content"
          className="flex-1 overflow-auto p-4 md:p-6 pb-20 md:pb-6"
        >
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
        <Footer />
      </div>
      <BottomNav />
      <CommandPalette />
    </div>
  );
}
