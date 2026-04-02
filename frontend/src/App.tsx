import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import { AuthGuard } from "./components/auth/AuthGuard";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const KnowledgeBase = lazy(() => import("./pages/KnowledgeBase"));
const ItemDetail = lazy(() => import("./pages/ItemDetail"));
const Search = lazy(() => import("./pages/Search"));
const Collections = lazy(() => import("./pages/Collections"));
const Tags = lazy(() => import("./pages/Tags"));
const Notes = lazy(() => import("./pages/Notes"));
const Settings = lazy(() => import("./pages/Settings"));
const AddItem = lazy(() => import("./pages/AddItem"));
const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const Admin = lazy(() => import("./pages/Admin"));
const SharedWithMe = lazy(() => import("./pages/SharedWithMe"));
const Feed = lazy(() => import("./pages/Feed"));
const PublicShare = lazy(() => import("./pages/PublicShare"));
const Rules = lazy(() => import("./pages/Rules"));
const Timeline = lazy(() => import("./pages/Timeline"));
const Highlights = lazy(() => import("./pages/Highlights"));

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-pulse text-sky-600 text-lg">Loading...</div>
    </div>
  );
}

function SuspenseWrap({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<LoadingFallback />}>{children}</Suspense>;
}

export default function App() {
  return (
    <Routes>
      {/* Public routes - no auth required */}
      <Route
        path="/login"
        element={<SuspenseWrap><Login /></SuspenseWrap>}
      />
      <Route
        path="/register"
        element={<SuspenseWrap><Register /></SuspenseWrap>}
      />

      {/* Protected routes - require authentication */}
      <Route element={<AuthGuard />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<SuspenseWrap><Dashboard /></SuspenseWrap>} />
          <Route path="/knowledge" element={<SuspenseWrap><KnowledgeBase /></SuspenseWrap>} />
          <Route path="/item/:id" element={<SuspenseWrap><ItemDetail /></SuspenseWrap>} />
          <Route path="/search" element={<SuspenseWrap><Search /></SuspenseWrap>} />
          <Route path="/collections" element={<SuspenseWrap><Collections /></SuspenseWrap>} />
          <Route path="/tags" element={<SuspenseWrap><Tags /></SuspenseWrap>} />
          <Route path="/notes" element={<SuspenseWrap><Notes /></SuspenseWrap>} />
          <Route path="/settings" element={<SuspenseWrap><Settings /></SuspenseWrap>} />
          <Route path="/add" element={<SuspenseWrap><AddItem /></SuspenseWrap>} />
          <Route path="/admin" element={<SuspenseWrap><Admin /></SuspenseWrap>} />
          <Route path="/shared" element={<SuspenseWrap><SharedWithMe /></SuspenseWrap>} />
          <Route path="/feed" element={<SuspenseWrap><Feed /></SuspenseWrap>} />
          <Route path="/rules" element={<SuspenseWrap><Rules /></SuspenseWrap>} />
          <Route path="/timeline" element={<SuspenseWrap><Timeline /></SuspenseWrap>} />
          <Route path="/highlights" element={<SuspenseWrap><Highlights /></SuspenseWrap>} />
        </Route>
      </Route>

      {/* Public share route - no auth required */}
      <Route path="/public/:token" element={<SuspenseWrap><PublicShare /></SuspenseWrap>} />
    </Routes>
  );
}
