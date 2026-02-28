# Decision: Set Azure Container App minReplicas to 1

**Author:** Jayne (Security Dev)
**Date:** 2026-02-27
**Status:** Implemented (pending deploy)

## Context
Users reported "I can't even login to the app" on Azure. Investigation revealed the Container App had `minReplicas: 0`, allowing it to scale to zero. The service worker masked the outage by serving cached static content, making the login form visible while all API calls timed out.

## Decision
Changed `minReplicas` from `0` to `1` in `infra/resources.bicep` to ensure at least one instance is always running.

## Trade-offs
- **Pro:** Login (and all API calls) work immediately without cold-start delay.
- **Con:** Slight cost increase — one container instance always running (~$5-10/mo for 0.5 CPU / 1Gi).

## Branch
`fix/azure-login-scale-to-zero`

## Next Steps
- Deploy with `azd provision` (to update infra) then `azd deploy` (to push latest code).
- Consider adding a frontend cold-start indicator if `minReplicas` is ever set back to 0.
