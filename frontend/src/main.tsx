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
import { msalConfig } from "./config/auth";
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
      retry: 1,
    },
  },
});

async function bootstrap(): Promise<void> {
  await msalInstance.initialize();

  let response;
  try {
    response = await msalInstance.handleRedirectPromise();
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
