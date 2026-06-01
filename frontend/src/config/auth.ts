import { Configuration, LogLevel } from "@azure/msal-browser";

import { env } from "./env";
import { logger } from "../lib/logger";

// RMP is single-tenant. A multi-tenant authority (/common, /organizations,
// /consumers) would offer sign-in to identities from any Entra tenant; the
// authority must be pinned to the configured tenant.
const MULTI_TENANT_AUTHORITY = /\/(common|organizations|consumers)\/?$/i;
if (MULTI_TENANT_AUTHORITY.test(env.azureAdAuthority)) {
  throw new Error(
    "VITE_AZURE_AD_AUTHORITY must be pinned to a specific Entra tenant, not a multi-tenant authority."
  );
}

const isMsalConfigured =
  env.azureAdClientId !== "" && env.azureAdAuthority !== "";

if (!isMsalConfigured) {
  logger.warn(
    "MSAL is not configured: VITE_AZURE_AD_CLIENT_ID and VITE_AZURE_AD_AUTHORITY must be set. Auth will be disabled."
  );
}

// L-1: in the production bundle, fail fast if the baked-in redirect URI points at
// a different origin than where the app is actually served (e.g. a bundle built
// with a staging/localhost redirect). Entra's reply-URL allow-list is the real
// control; this is a cheap defensive boot check.
if (import.meta.env.PROD && isMsalConfigured && env.azureAdRedirectUri) {
  if (new URL(env.azureAdRedirectUri).origin !== window.location.origin) {
    throw new Error(
      "Build misconfiguration: VITE_AZURE_AD_REDIRECT_URI origin does not match the window origin."
    );
  }
}

export { isMsalConfigured };

export const msalConfig: Configuration = {
  auth: {
    clientId: env.azureAdClientId,
    authority: env.azureAdAuthority,
    redirectUri: env.azureAdRedirectUri,
    postLogoutRedirectUri: env.azureAdRedirectUri,
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      // H-15: Verbose forwards account UPNs, scopes, and token-cache events to
      // the console. Keep it quiet in the production bundle.
      logLevel: import.meta.env.PROD ? LogLevel.Error : LogLevel.Info,
      piiLoggingEnabled: false,
      loggerCallback: (_level, message) => {
        logger.debug(message);
      },
    },
  },
};

export const loginRequest = {
  scopes: ["User.Read"],
  prompt: "select_account" as const,
};

export const apiTokenRequest = {
  scopes: env.apiScope
    ? [env.apiScope]
    : [`api://${env.azureAdClientId}/access_as_user`],
};
