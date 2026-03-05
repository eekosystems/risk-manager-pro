import { useIsAuthenticated } from "@azure/msal-react";
import { Shield } from "lucide-react";
import { Navigate } from "react-router-dom";

import { useAuth } from "@/hooks/use-auth";

export function LoginPage() {
  const { login } = useAuth();
  const isAuthenticated = useIsAuthenticated();

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-gray-50 to-brand-50">
      <div className="w-full max-w-md rounded-2xl bg-white p-10 shadow-xl">
        <div className="mb-8 flex flex-col items-center">
          <img
            src="/logo.webp"
            alt="Risk Manager Pro"
            className="mb-4 h-auto w-[200px]"
          />
          <h1 className="text-2xl font-bold text-gray-900">
            Risk Manager <span className="text-brand-500">Pro</span>
          </h1>
          <p className="mt-2 text-center text-sm text-gray-500">
            AI-powered aviation safety risk management
          </p>
        </div>

        <button
          onClick={() => void login()}
          className="flex w-full items-center justify-center gap-3 rounded-xl bg-gradient-to-r from-brand-500 to-brand-400 px-6 py-3.5 font-semibold text-white shadow-lg shadow-brand-500/25 transition-all hover:shadow-xl hover:shadow-brand-500/30"
        >
          <Shield size={20} />
          Sign in with Microsoft
        </button>

        <p className="mt-6 text-center text-xs text-gray-400">
          Protected by Microsoft Entra ID
        </p>
      </div>
    </div>
  );
}
