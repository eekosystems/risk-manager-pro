# Pre-provision hook for Azure Developer CLI (azd)
# Generates a secure database password if one is not already set.

$ErrorActionPreference = "Stop"

$dbPassword = azd env get-value DB_ADMIN_PASSWORD 2>$null
if (-not $dbPassword) {
    Write-Host "Generating secure database admin password..."
    $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    $password = -join (1..32 | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
    azd env set DB_ADMIN_PASSWORD $password
    Write-Host "Database password generated and stored in azd environment."
} else {
    Write-Host "Database password already set. Skipping."
}
