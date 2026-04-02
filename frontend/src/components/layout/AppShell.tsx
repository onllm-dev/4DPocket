import { Outlet } from "react-router-dom";
import { BottomNav } from "./BottomNav";
import { Footer } from "./Footer";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { CommandPalette } from "@/components/common/CommandPalette";
import { useKeyboardShortcuts } from "@/hooks/use-keyboard";

export function AppShell() {
  useKeyboardShortcuts();

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-auto p-4 md:p-6 pb-20 md:pb-6 animate-fade-in">
          <Outlet />
          <Footer />
        </main>
      </div>
      <BottomNav />
      <CommandPalette />
    </div>
  );
}
