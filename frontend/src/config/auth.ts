import { Configuration, LogLevel } from "@azure/msal-browser";

import { env } from "./env";
import { logger } from "../lib/logger";

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
