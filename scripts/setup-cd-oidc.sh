#!/usr/bin/env bash
# Setup OIDC Service Principal for CD pipeline
# Run this once to create the SP and add the GitHub secret.
#
# Prerequisites:
#   - az cli logged in with permissions to create app registrations
#   - gh cli logged in to ericchansen/itemwise
#
# Usage: bash scripts/setup-cd-oidc.sh

set -euo pipefail

REPO="ericchansen/itemwise"
APP_NAME="itemwise-gha-cd-prod"
SUBSCRIPTION_ID="9450bd3b-96c5-48b2-bfdf-3374304efbd7"
RESOURCE_GROUP="rg-itemwise-prod"
TENANT_ID="9c74def4-ef0a-418a-8dc7-1e7a1e85ce10"

echo "==> Creating Entra ID app registration: $APP_NAME"
APP_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)
echo "    App (client) ID: $APP_ID"

echo "==> Creating service principal"
SP_OBJECT_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv)
echo "    SP object ID: $SP_OBJECT_ID"

echo "==> Adding federated credential for ref:refs/heads/master"
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-master-push",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:'"$REPO"':ref:refs/heads/master",
  "audiences": ["api://AzureADTokenExchange"],
  "description": "GitHub Actions CD on push to master"
}'

echo "==> Assigning Contributor role on resource group"
az role assignment create \
  --assignee-object-id "$SP_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role Contributor \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"

echo "==> Assigning AcrPush role on container registry"
ACR_ID=$(az acr list --resource-group "$RESOURCE_GROUP" --query "[0].id" -o tsv)
az role assignment create \
  --assignee-object-id "$SP_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role AcrPush \
  --scope "$ACR_ID"

echo "==> Setting GitHub secret AZURE_CD_CLIENT_ID"
gh secret set AZURE_CD_CLIENT_ID --repo "$REPO" --body "$APP_ID"

echo ""
echo "Done! The CD pipeline will use:"
echo "  AZURE_CD_CLIENT_ID = $APP_ID"
echo "  AZURE_TENANT_ID    = $TENANT_ID (already set)"
echo "  AZURE_SUBSCRIPTION_ID = $SUBSCRIPTION_ID (already set)"
