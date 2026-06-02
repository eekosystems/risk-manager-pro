import { InteractionStatus } from "@azure/msal-browser";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { useInactivityTimeout } from "@/hooks/use-inactivity-timeout";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const isAuthenticated = useIsAuthenticated();
  const { instance, inProgress } = useMsal();
  // L-7: when the inactivity timer is about to fire, warn the user instead of
  // silently logging them out. `deadline` is the wall-clock time of logout.
  const [warningDeadline, setWarningDeadline] = useState<number | null>(null);

  const handleInactivityTimeout = useCallback(async () => {
    await instance.logoutRedirect({
      account: instance.getActiveAccount(),
      postLogoutRedirectUri: "/login",
    });
  }, [instance]);

  const handleWarning = useCallback((secondsRemaining: number) => {
    setWarningDeadline(Date.now() + secondsRemaining * 1000);
  }, []);

  const handleActive = useCallback(() => {
    setWarningDeadline(null);
  }, []);

  useInactivityTimeout({
    onTimeout: handleInactivityTimeout,
    onWarning: handleWarning,
    onActive: handleActive,
  });

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

  return (
    <>
      {children}
      {warningDeadline !== null && (
        <InactivityWarning
          deadline={warningDeadline}
          onStay={() => setWarningDeadline(null)}
        />
      )}
    </>
  );
}

interface InactivityWarningProps {
  deadline: number;
  onStay: () => void;
}

function InactivityWarning({ deadline, onStay }: InactivityWarningProps) {
  const [remaining, setRemaining] = useState(() =>
    Math.max(0, Math.round((deadline - Date.now()) / 1000))
  );

  useEffect(() => {
    const id = setInterval(() => {
      setRemaining(Math.max(0, Math.round((deadline - Date.now()) / 1000)));
    }, 1000);
    return () => clearInterval(id);
  }, [deadline]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="inactivity-warning-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="mx-4 w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
        <h2
          id="inactivity-warning-title"
          className="text-lg font-semibold text-gray-900"
        >
          Still there?
        </h2>
        <p className="mt-2 text-sm text-gray-600">
          You'll be signed out in {remaining}s due to inactivity.
        </p>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onStay}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Stay signed in
          </button>
        </div>
      </div>
    </div>
  );
}
