import {
  EventType,
  type AuthenticationResult,
  type EventMessage,
  PublicClientApplication,
} from "@azure/msal-browser";
import { MsalProvider } from "@azure/msal-react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./app";
import { ToastProvider } from "./components/ui/toast";
import { isMsalConfigured, msalConfig } from "./config/auth";
import { OrganizationProvider } from "./context/organization-context";
import "./index.css";
import { setMsalInstance } from "./lib/api-client";
import { logger } from "./lib/logger";

const msalInstance = new PublicClientApplication(msalConfig);
setMsalInstance(msalInstance);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error) => {
        // Never retry rate-limited or auth requests
        const status = (error as { status?: number }).status;
        if (status === 429 || status === 401 || status === 403) return false;
        return failureCount < 1;
      },
      refetchOnWindowFocus: false,
    },
  },
});

async function bootstrap(): Promise<void> {
  await msalInstance.initialize();

  if (!isMsalConfigured) {
    logger.warn(
      "[auth] Skipping MSAL login flow — set VITE_AZURE_AD_CLIENT_ID and VITE_AZURE_AD_AUTHORITY in .env"
    );
  }

  let response;
  try {
    response = isMsalConfigured
      ? await msalInstance.handleRedirectPromise()
      : null;
  } catch (err) {
    logger.error("[auth] handleRedirectPromise failed — clearing session cache:", err);
    sessionStorage.clear();
  }
  if (response?.account) {
    msalInstance.setActiveAccount(response.account);
  }

  if (!msalInstance.getActiveAccount()) {
    const accounts = msalInstance.getAllAccounts();
    if (accounts.length > 0) {
      msalInstance.setActiveAccount(accounts[0] ?? null);
    }
  }

  msalInstance.addEventCallback((event: EventMessage) => {
    if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
      const result = event.payload as AuthenticationResult;
      if (result.account) {
        msalInstance.setActiveAccount(result.account);
      }
    }
  });

  const root = document.getElementById("root");
  if (!root) throw new Error("Root element not found");

  createRoot(root).render(
    <StrictMode>
      <MsalProvider instance={msalInstance}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <ToastProvider>
              <OrganizationProvider>
                <App />
              </OrganizationProvider>
            </ToastProvider>
          </BrowserRouter>
        </QueryClientProvider>
      </MsalProvider>
    </StrictMode>,
  );
}

void bootstrap();
