import {
  InteractionRequiredAuthError,
  type IPublicClientApplication,
} from "@azure/msal-browser";
import axios from "axios";

import { apiTokenRequest } from "@/config/auth";
import { env } from "@/config/env";

export const apiClient = axios.create({
  baseURL: `${env.apiBaseUrl}/api/v1`,
  headers: { "Content-Type": "application/json" },
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

apiClient.interceptors.request.use(async (config) => {
  if (!msalInstance) return config;

  const accounts = msalInstance.getAllAccounts();
  if (accounts.length === 0) return config;

  try {
    const response = await msalInstance.acquireTokenSilent({
      ...apiTokenRequest,
      account: accounts[0],
    });
    config.headers.Authorization = `Bearer ${response.accessToken}`;
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      await msalInstance.acquireTokenRedirect(apiTokenRequest);
    }
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
      if (msalInstance) {
        msalInstance.acquireTokenRedirect(apiTokenRequest).catch(console.error);
      }
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
