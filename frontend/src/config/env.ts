interface EnvConfig {
  apiBaseUrl: string;
  azureAdClientId: string;
  azureAdAuthority: string;
  azureAdRedirectUri: string;
  apiScope: string;
}

export const env: EnvConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  azureAdClientId: import.meta.env.VITE_AZURE_AD_CLIENT_ID ?? "",
  azureAdAuthority: import.meta.env.VITE_AZURE_AD_AUTHORITY ?? "",
  azureAdRedirectUri: import.meta.env.VITE_AZURE_AD_REDIRECT_URI ?? "http://localhost:5173",
  apiScope: import.meta.env.VITE_API_SCOPE ?? "",
};
