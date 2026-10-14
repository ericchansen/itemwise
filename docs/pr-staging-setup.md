# Production and PR staging retirement

The `itemwise-prod` demo is being retired. Production CD and PR staging workflows
have been removed; successful CI runs and pull request events no longer provision
or deploy into `rg-itemwise-prod`.

This source change does not remove existing Container Apps, PostgreSQL databases,
registry images, identities, or Azure resources. An authorized owner must inspect
shared dependencies and perform the approved teardown. Removing the PR workflow
also removes its automatic close-event cleanup; existing `ca-pr-*` apps and
`inventory_pr_*` databases must be included in that teardown.

Do not create production/staging federated credentials or role assignments for
these retired workflows. Existing credentials and permissions require a separate
ownership review; this change does not revoke shared access.

Local development and [CI](../.github/workflows/ci.yml) remain supported.
The [Bicep infrastructure](../infra/main.bicep) and [azd configuration](../azure.yaml)
are reusable samples, not an instruction to recreate the retired production
environment. Provision a new, explicitly chosen environment only when a new
deployment is authorized.
