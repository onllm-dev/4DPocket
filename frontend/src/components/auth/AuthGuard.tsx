import { Navigate, Outlet } from "react-router-dom";
import { isLoggedIn } from "@/api/client";
import { useCurrentUser } from "@/hooks/use-auth";
import { Loader2 } from "lucide-react";

export function AuthGuard() {
  const loggedIn = isLoggedIn();
  const { isLoading, isError } = useCurrentUser();

  if (!loggedIn) {
    return <Navigate to="/login" replace />;
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-950">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-sky-600" />
          <span className="text-sm text-gray-500">Loading...</span>
        </div>
      </div>
    );
  }

  if (isError) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
