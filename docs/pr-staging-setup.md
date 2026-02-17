# PR Staging Setup (Azure + GitHub Actions OIDC)

This repository can deploy an ephemeral Azure staging app for each PR using `.github/workflows/pr-staging.yml`.

## What gets created per PR

- Container App: `ca-pr-<pr-number>`
- PostgreSQL database: `inventory_pr_<pr-number>`
- ACR image tag: `itemwise:pr-<pr-number>`

All three are cleaned up automatically when the PR is closed.

## One-time Azure setup

### 1) Create an Entra app registration

1. Go to **Microsoft Entra ID** -> **App registrations** -> **New registration**.
2. Name it `itemwise-gha-pr-staging` (or similar).
3. Keep single-tenant defaults and create it.
4. Copy the **Application (client) ID** and **Directory (tenant) ID**.

### 2) Add GitHub federated credential (OIDC)

In the app registration:

1. Open **Certificates & secrets** -> **Federated credentials** -> **Add credential**.
2. Select **GitHub Actions deploying Azure resources**.
3. Configure:
   - **Organization**: `erichansen`
   - **Repository**: `itemwise`
   - **Entity type**: `Pull request`
   - **Name**: `itemwise-pr-staging`
4. Save.

This allows GitHub Actions to request Azure tokens without storing Azure secrets.

### 3) Grant Azure RBAC permissions

Assign the app registration service principal:

- **Contributor** on resource group `rg-itemwise-prod`
- **AcrPush** on the existing ACR in that resource group

Example CLI:

```bash
az role assignment create \
  --assignee <APP_CLIENT_ID> \
  --role Contributor \
  --scope /subscriptions/9450bd3b-96c5-48b2-bfdf-3374304efbd7/resourceGroups/rg-itemwise-prod

az role assignment create \
  --assignee <APP_CLIENT_ID> \
  --role AcrPush \
  --scope /subscriptions/9450bd3b-96c5-48b2-bfdf-3374304efbd7/resourceGroups/rg-itemwise-prod/providers/Microsoft.ContainerRegistry/registries/<ACR_NAME>
```

## One-time GitHub setup

Add these repository secrets in **Settings -> Secrets and variables -> Actions**:

- `AZURE_CLIENT_ID` = app registration client ID
- `AZURE_TENANT_ID` = tenant ID
- `AZURE_SUBSCRIPTION_ID` = `9450bd3b-96c5-48b2-bfdf-3374304efbd7`
- `POSTGRES_ADMIN_PASSWORD` = PostgreSQL admin password for `inventoryadmin`

## How the workflow behaves

- On PR `opened`, `synchronize`, `reopened`:
  - Builds/pushes `itemwise:pr-<number>` to ACR
  - Recreates `inventory_pr_<number>` database
  - Recreates `ca-pr-<number>` container app in existing shared infra
  - Runs E2E tests against that staging URL
  - Posts/updates a PR comment with staging URL and E2E status

- On PR `closed`:
  - Deletes `ca-pr-<number>`
  - Deletes `inventory_pr_<number>`
  - Deletes image tag `itemwise:pr-<number>`

## Notes

- This workflow intentionally skips fork PRs because it requires Azure permissions.
- If PostgreSQL is auto-stopped, the workflow starts it before DB operations.
