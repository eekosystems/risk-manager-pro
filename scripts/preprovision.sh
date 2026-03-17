#!/bin/sh
# -------------------------------------------------------------------
# Pre-provision hook for Azure Developer CLI (azd)
# Generates a secure database password if one is not already set.
# -------------------------------------------------------------------
set -e

if [ -z "$DB_ADMIN_PASSWORD" ]; then
  echo "Generating secure database admin password..."
  # 32-char password with mixed case, digits, and special chars
  DB_ADMIN_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
  azd env set DB_ADMIN_PASSWORD "$DB_ADMIN_PASSWORD"
  echo "Database password generated and stored in azd environment."
fi
