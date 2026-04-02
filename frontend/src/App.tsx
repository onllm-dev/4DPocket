import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const KnowledgeBase = lazy(() => import("./pages/KnowledgeBase"));
const ItemDetail = lazy(() => import("./pages/ItemDetail"));
const Search = lazy(() => import("./pages/Search"));
const Collections = lazy(() => import("./pages/Collections"));
const Tags = lazy(() => import("./pages/Tags"));
const Notes = lazy(() => import("./pages/Notes"));
const Settings = lazy(() => import("./pages/Settings"));
const AddItem = lazy(() => import("./pages/AddItem"));

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-pulse text-[var(--color-primary)] text-lg">
        Loading...
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route
          path="/"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <Dashboard />
            </Suspense>
          }
        />
        <Route
          path="/knowledge"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <KnowledgeBase />
            </Suspense>
          }
        />
        <Route
          path="/item/:id"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <ItemDetail />
            </Suspense>
          }
        />
        <Route
          path="/search"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <Search />
            </Suspense>
          }
        />
        <Route
          path="/collections"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <Collections />
            </Suspense>
          }
        />
        <Route
          path="/tags"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <Tags />
            </Suspense>
          }
        />
        <Route
          path="/notes"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <Notes />
            </Suspense>
          }
        />
        <Route
          path="/settings"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <Settings />
            </Suspense>
          }
        />
        <Route
          path="/add"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <AddItem />
            </Suspense>
          }
        />
      </Route>
    </Routes>
  );
}
