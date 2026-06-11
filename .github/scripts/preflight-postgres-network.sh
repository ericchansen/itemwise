#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${AZURE_RESOURCE_GROUP:-}" ]]; then
  echo "AZURE_RESOURCE_GROUP is required"
  exit 1
fi

if [[ -z "${PG_SERVER:-}" ]]; then
  echo "PG_SERVER is required"
  exit 1
fi

require_private="${REQUIRE_PRIVATE_POSTGRES:-false}"
server_json="$(az postgres flexible-server show \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$PG_SERVER" \
  --query "{state:state,publicNetworkAccess:network.publicNetworkAccess,id:id}" -o json)"

state="$(echo "$server_json" | jq -r '.state')"
public_network_access="$(echo "$server_json" | jq -r '.publicNetworkAccess')"
server_id="$(echo "$server_json" | jq -r '.id')"

if [[ "$state" != "Ready" ]]; then
  echo "Preflight failed: PostgreSQL server $PG_SERVER is not Ready (state=$state)"
  exit 1
fi

if [[ "$require_private" == "true" ]]; then
  if [[ "$public_network_access" != "Disabled" ]]; then
    echo "Preflight failed: PostgreSQL publicNetworkAccess must be Disabled (actual=$public_network_access)"
    exit 1
  fi

  pe_count="$(az network private-endpoint list \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --query "[?contains(properties.privateLinkServiceConnections[0].properties.privateLinkServiceId, '$server_id')].name | length(@)" -o tsv)"
  if [[ "${pe_count:-0}" -lt 1 ]]; then
    echo "Preflight failed: No private endpoint found for PostgreSQL server $PG_SERVER"
    exit 1
  fi

  firewall_rule_count="$(az postgres flexible-server firewall-rule list \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$PG_SERVER" \
    --query "length(@)" -o tsv)"
  if [[ "${firewall_rule_count:-0}" -gt 0 ]]; then
    echo "Preflight failed: Firewall rules still exist on a private-only PostgreSQL server"
    exit 1
  fi
fi

echo "PostgreSQL preflight passed (require_private=$require_private, publicNetworkAccess=$public_network_access)"
