import { Configuration, LogLevel } from "@azure/msal-browser";

import { env } from "./env";

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
      logLevel: LogLevel.Warning,
      loggerCallback: (level, message) => {
        if (level === LogLevel.Error) {
          console.error(message);
        }
      },
    },
  },
};

export const loginRequest = {
  scopes: env.apiScope ? [env.apiScope] : ["User.Read"],
};

export const apiTokenRequest = {
  scopes: env.apiScope ? [env.apiScope] : [],
};
