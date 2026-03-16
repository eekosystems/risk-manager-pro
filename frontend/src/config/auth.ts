import { Configuration, LogLevel } from "@azure/msal-browser";

import { env } from "./env";
import { logger } from "../lib/logger";

const isMsalConfigured =
  env.azureAdClientId !== "" && env.azureAdAuthority !== "";

if (!isMsalConfigured) {
  logger.warn(
    "MSAL is not configured: VITE_AZURE_AD_CLIENT_ID and VITE_AZURE_AD_AUTHORITY must be set. Auth will be disabled."
  );
}

export { isMsalConfigured };

export const msalConfig: Configuration = {
  auth: {
    clientId: env.azureAdClientId || "00000000-0000-0000-0000-000000000000",
    authority:
      env.azureAdAuthority ||
      "https://login.microsoftonline.com/common",
    redirectUri: env.azureAdRedirectUri,
    postLogoutRedirectUri: env.azureAdRedirectUri,
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Verbose,
      loggerCallback: (_level, message) => {
        logger.debug(message);
      },
    },
  },
};

export const loginRequest = {
  scopes: ["User.Read"],
};

export const apiTokenRequest = {
  scopes: env.apiScope
    ? [env.apiScope]
    : [`api://${env.azureAdClientId}/access_as_user`],
};
