import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext";

export function ProtectedRoute({ requiredRole }: { requiredRole?: "SUPER-ADMIN" | "ADMIN" }) {
  const { isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <p className="p-8">Loading authentication state…</p>;
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (requiredRole && !user.roles.some((role) => role.name === requiredRole)) {
    return <Navigate to="/forbidden" replace />;
  }
  return <Outlet />;
}
