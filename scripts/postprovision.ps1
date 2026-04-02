# Post-provision hook for Azure Developer CLI (azd)
# Skips app registration if client ID is already set (created manually).

$ErrorActionPreference = "Stop"

$clientId = azd env get-value AZURE_AD_CLIENT_ID 2>$null
if ($clientId) {
    Write-Host "Entra ID app registration already configured (client ID: $clientId). Skipping."
    exit 0
}

$webUrl = azd env get-value SERVICE_WEB_URI 2>$null

Write-Host "Creating Entra ID app registration for Risk Manager Pro..."

$appJson = az ad app create `
    --display-name "Risk Manager Pro" `
    --sign-in-audience "AzureADMyOrg" `
    --web-redirect-uris "https://$webUrl" "http://localhost:5173" `
    --enable-id-token-issuance true `
    --enable-access-token-issuance false `
    --output json

$app = $appJson | ConvertFrom-Json
$newClientId = $app.appId
$objectId = $app.id

Write-Host "App registration created: $newClientId"

# Add API scope (access_as_user)
$scopeId = [guid]::NewGuid().ToString()
az ad app update `
    --id $objectId `
    --identifier-uris "api://$newClientId" `
    --set "api={`"oauth2PermissionScopes`":[{`"adminConsentDescription`":`"Access Risk Manager Pro API`",`"adminConsentDisplayName`":`"Access API`",`"id`":`"$scopeId`",`"isEnabled`":true,`"type`":`"User`",`"userConsentDescription`":`"Access Risk Manager Pro API`",`"userConsentDisplayName`":`"Access API`",`"value`":`"access_as_user`"}]}"

Write-Host "API scope 'access_as_user' configured."

# Create service principal
az ad sp create --id $newClientId --output none 2>$null

Write-Host "Service principal created."

# Store values back into azd environment
azd env set AZURE_AD_CLIENT_ID $newClientId
$tenantId = az account show --query tenantId -o tsv
azd env set AZURE_AD_TENANT_ID $tenantId

Write-Host ""
Write-Host "Entra ID app registration complete."
Write-Host "  Client ID:  $newClientId"
Write-Host "  Tenant ID:  $tenantId"
Write-Host "  Redirect:   https://$webUrl"
Write-Host ""
Write-Host "IMPORTANT: Grant admin consent in the Azure Portal:"
Write-Host "  Azure Portal > App registrations > Risk Manager Pro > API permissions > Grant admin consent"
