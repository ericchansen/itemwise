#!/usr/bin/env bash
set -euo pipefail

: "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"

export MSYS_NO_PATHCONV=1

AZ_SUBSCRIPTION_ARGS=()
if [[ -n "${AZURE_SUBSCRIPTION_ID:-}" ]]; then
  AZ_SUBSCRIPTION_ARGS=(--subscription "$AZURE_SUBSCRIPTION_ID")
fi

APP_NAME="${CONTAINER_APP_NAME:-}"
if [[ -z "$APP_NAME" ]]; then
  APP_NAME="$(az containerapp list \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    "${AZ_SUBSCRIPTION_ARGS[@]}" \
    --query "[?starts_with(name, 'ca-api-')] | [0].name" \
    -o tsv)"
fi

if [[ -z "$APP_NAME" ]]; then
  echo "Failed to discover Container App in $AZURE_RESOURCE_GROUP"
  exit 1
fi

APP_JSON="$(az containerapp show --resource-group "$AZURE_RESOURCE_GROUP" --name "$APP_NAME" "${AZ_SUBSCRIPTION_ARGS[@]}" -o json)"
ENV_CLIENT_ID="$(jq -r '.properties.template.containers[0].env[]? | select(.name == "AZURE_CLIENT_ID") | .value // empty' <<<"$APP_JSON")"
OPENAI_ENDPOINT="$(jq -r '.properties.template.containers[0].env[]? | select(.name == "AZURE_OPENAI_ENDPOINT") | .value // empty' <<<"$APP_JSON")"

if [[ -z "$OPENAI_ENDPOINT" ]]; then
  echo "Azure OpenAI endpoint is not configured on $APP_NAME; identity preflight not required."
  exit 0
fi

IDENTITIES_JSON="$(jq -c '.identity.userAssignedIdentities // {}' <<<"$APP_JSON")"
if [[ "$IDENTITIES_JSON" == "{}" ]]; then
  echo "$APP_NAME has Azure OpenAI configured but no user-assigned managed identity attached."
  exit 1
fi

if [[ -z "$ENV_CLIENT_ID" ]]; then
  echo "$APP_NAME has Azure OpenAI configured but AZURE_CLIENT_ID is empty."
  exit 1
fi

MATCHING_IDENTITY="$(jq -r --arg clientId "$ENV_CLIENT_ID" '
  to_entries[]
  | select(.value.clientId == $clientId)
  | .key
' <<<"$IDENTITIES_JSON" | head -n 1)"

if [[ -z "$MATCHING_IDENTITY" ]]; then
  echo "$APP_NAME AZURE_CLIENT_ID=$ENV_CLIENT_ID does not match any assigned user-managed identity."
  echo "Run azd provision so IaC rewrites AZURE_CLIENT_ID from the attached managed identity."
  jq -r 'to_entries[] | "assigned identity: \(.key) clientId=\(.value.clientId)"' <<<"$IDENTITIES_JSON"
  exit 1
fi

PRINCIPAL_ID="$(jq -r --arg clientId "$ENV_CLIENT_ID" '
  to_entries[]
  | select(.value.clientId == $clientId)
  | .value.principalId
' <<<"$IDENTITIES_JSON" | head -n 1)"
OPENAI_ID="$(az cognitiveservices account list \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  "${AZ_SUBSCRIPTION_ARGS[@]}" \
  --query "[?kind=='OpenAI' && properties.endpoint=='$OPENAI_ENDPOINT'] | [0].id" \
  -o tsv)"

if [[ -z "$OPENAI_ID" ]]; then
  echo "No Azure OpenAI account in $AZURE_RESOURCE_GROUP matches endpoint $OPENAI_ENDPOINT"
  exit 1
fi

ROLE_COUNT="$(az role assignment list \
  --scope "$OPENAI_ID" \
  "${AZ_SUBSCRIPTION_ARGS[@]}" \
  --query "[?principalId=='$PRINCIPAL_ID' && roleDefinitionId && contains(roleDefinitionId, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')] | length(@)" \
  -o tsv)"

if [[ "$ROLE_COUNT" == "0" ]]; then
  echo "Managed identity $MATCHING_IDENTITY is missing Cognitive Services OpenAI User on $OPENAI_ID"
  echo "Run azd provision to apply the IaC role assignment."
  exit 1
fi

echo "Azure OpenAI identity preflight passed for $APP_NAME using $MATCHING_IDENTITY"
