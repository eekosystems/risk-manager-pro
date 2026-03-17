interface EnvConfig {
  apiBaseUrl: string;
  azureAdClientId: string;
  azureAdAuthority: string;
  azureAdRedirectUri: string;
  apiScope: string;
}

function requireEnv(key: string): string {
  const value = import.meta.env[key] as string | undefined;
  if (!value) {
    throw new Error(`Missing required environment variable: ${key}`);
  }
  return value;
}

export const env: EnvConfig = {
  apiBaseUrl: requireEnv("VITE_API_BASE_URL"),
  azureAdClientId: requireEnv("VITE_AZURE_AD_CLIENT_ID"),
  azureAdAuthority: requireEnv("VITE_AZURE_AD_AUTHORITY"),
  azureAdRedirectUri: requireEnv("VITE_AZURE_AD_REDIRECT_URI"),
  apiScope: requireEnv("VITE_API_SCOPE"),
};
