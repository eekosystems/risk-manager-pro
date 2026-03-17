#!/bin/sh
# -------------------------------------------------------------------
# Post-provision hook for Azure Developer CLI (azd)
# Creates the Entra ID app registration for MSAL authentication
# and stores the client ID back into the azd environment.
# -------------------------------------------------------------------
set -e

TENANT_ID=$(azd env get-value AZURE_AD_TENANT_ID 2>/dev/null || echo "")
CLIENT_ID=$(azd env get-value AZURE_AD_CLIENT_ID 2>/dev/null || echo "")
API_URL=$(azd env get-value SERVICE_API_URI 2>/dev/null || echo "")
WEB_URL=$(azd env get-value SERVICE_WEB_URI 2>/dev/null || echo "")

# If client ID is already set, skip app registration
if [ -n "$CLIENT_ID" ]; then
  echo "Entra ID app registration already configured (client ID: $CLIENT_ID). Skipping."
  exit 0
fi

echo "Creating Entra ID app registration for Risk Manager Pro..."

# Create the app registration
APP_JSON=$(az ad app create \
  --display-name "Risk Manager Pro" \
  --sign-in-audience "AzureADMyOrg" \
  --web-redirect-uris "https://${WEB_URL}" "http://localhost:5173" \
  --enable-id-token-issuance true \
  --enable-access-token-issuance false \
  --output json)

CLIENT_ID=$(echo "$APP_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['appId'])")
OBJECT_ID=$(echo "$APP_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "App registration created: $CLIENT_ID"

# Add API scope (access_as_user)
az ad app update \
  --id "$OBJECT_ID" \
  --identifier-uris "api://$CLIENT_ID" \
  --set "api={\"oauth2PermissionScopes\":[{\"adminConsentDescription\":\"Access Risk Manager Pro API\",\"adminConsentDisplayName\":\"Access API\",\"id\":\"$(python3 -c "import uuid; print(uuid.uuid4())")\",\"isEnabled\":true,\"type\":\"User\",\"userConsentDescription\":\"Access Risk Manager Pro API\",\"userConsentDisplayName\":\"Access API\",\"value\":\"access_as_user\"}]}"

echo "API scope 'access_as_user' configured."

# Create service principal for the app
az ad sp create --id "$CLIENT_ID" --output none 2>/dev/null || true
echo "Service principal created."

# Store values back into azd environment
azd env set AZURE_AD_CLIENT_ID "$CLIENT_ID"
azd env set AZURE_AD_TENANT_ID "$(az account show --query tenantId -o tsv)"

echo ""
echo "Entra ID app registration complete."
echo "  Client ID:  $CLIENT_ID"
echo "  Tenant ID:  $(az account show --query tenantId -o tsv)"
echo "  Redirect:   https://${WEB_URL}"
echo ""
echo "IMPORTANT: Grant admin consent in the Azure Portal:"
echo "  Azure Portal > App registrations > Risk Manager Pro > API permissions > Grant admin consent"
