import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { useCallback } from "react";

import { loginRequest } from "@/config/auth";

interface AuthState {
  isAuthenticated: boolean;
  userName: string | null;
  userEmail: string | null;
  login: () => Promise<void>;
  logout: () => Promise<void>;
}

export function useAuth(): AuthState {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  const account = accounts[0] ?? null;

  const login = useCallback(async () => {
    await instance.loginRedirect(loginRequest);
  }, [instance]);

  const logout = useCallback(async () => {
    await instance.logoutRedirect({
      account: instance.getActiveAccount(),
    });
  }, [instance]);

  return {
    isAuthenticated,
    userName: account?.name ?? null,
    userEmail: account?.username ?? null,
    login,
    logout,
  };
}
