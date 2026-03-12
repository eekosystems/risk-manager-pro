import { type IPublicClientApplication } from "@azure/msal-browser";
import axios from "axios";

import { apiTokenRequest } from "@/config/auth";
import { env } from "@/config/env";

export const apiClient = axios.create({
  baseURL: `${env.apiBaseUrl}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

let msalInstance: IPublicClientApplication | null = null;
let activeOrganizationId: string | null = null;

export function setMsalInstance(instance: IPublicClientApplication): void {
  msalInstance = instance;
}

export function setActiveOrganizationId(orgId: string | null): void {
  activeOrganizationId = orgId;
}

export function getActiveOrganizationId(): string | null {
  return activeOrganizationId;
}

const TOKEN_TIMEOUT_MS = 10_000;

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("Token acquisition timed out")), ms),
    ),
  ]);
}

apiClient.interceptors.request.use(async (config) => {
  if (!msalInstance) return config;

  const accounts = msalInstance.getAllAccounts();
  if (accounts.length === 0) return config;

  try {
    const response = await withTimeout(
      msalInstance.acquireTokenSilent({
        ...apiTokenRequest,
        account: accounts[0],
      }),
      TOKEN_TIMEOUT_MS,
    );
    config.headers.Authorization = `Bearer ${response.accessToken}`;
  } catch (error) {
    console.error("[api-client] Token acquisition failed:", error);
  }

  if (activeOrganizationId) {
    config.headers["X-Organization-ID"] = activeOrganizationId;
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      console.warn("[api-client] 401 response — user may need to re-login");
    }
    return Promise.reject(error);
  },
);

export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await axios.get(`${env.apiBaseUrl}/api/v1/health`);
    return response.data?.status === "healthy";
  } catch {
    return false;
  }
}
