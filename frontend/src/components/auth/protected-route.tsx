import { InteractionStatus } from "@azure/msal-browser";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { useCallback } from "react";
import { Navigate } from "react-router-dom";

import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { useInactivityTimeout } from "@/hooks/use-inactivity-timeout";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const isAuthenticated = useIsAuthenticated();
  const { instance, inProgress } = useMsal();

  const handleInactivityTimeout = useCallback(async () => {
    await instance.logoutRedirect({
      postLogoutRedirectUri: "/login",
    });
  }, [instance]);

  useInactivityTimeout({ onTimeout: handleInactivityTimeout });

  if (inProgress !== InteractionStatus.None) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-4">
          <img src="/logo.webp" alt="Risk Manager Pro" className="h-12 w-12" />
          <LoadingSpinner size="lg" />
          <p className="text-sm font-medium text-gray-500">
            Authenticating...
          </p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
