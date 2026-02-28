# Decision: Add GitHub Environments to CI/CD Workflows

**Author:** Simon (DevOps)
**Date:** 2026-02-28
**Status:** Implemented

## Context

Deployments were not visible in the GitHub repository sidebar because the workflow jobs lacked the `environment:` key. This was identified during the teamskills comparison (see history).

## Decision

1. Added `environment: production` (with `url`) to the `deploy` job in `.github/workflows/cd.yml`
2. Added `environment: staging` (with dynamic `url` from staging step output) to the `deploy-and-test` job in `.github/workflows/pr-staging.yml`
3. Created both environments in GitHub via `gh api --method PUT`
4. Added a deployment summary step to `cd.yml` that writes to `$GITHUB_STEP_SUMMARY`

## Rationale

- GitHub Environments enable deployment tracking in the repo sidebar
- The `url` property makes each deployment clickable, linking directly to the deployed app
- The deployment summary step provides at-a-glance info in the Actions run page
- No structural changes to workflows — minimal additions only

## Impact

- All future CD runs will register as production deployments
- All future PR staging deploys will register as staging deployments
- Deployment history will be visible at: https://github.com/ericchansen/itemwise/deployments
