# Decision: Image Lifecycle Tests Required

**Author:** Zoe (Tester)  
**Date:** 2026-03-01  
**Status:** Implemented

## Context

A critical frontend bug shipped where `clearImagePreview()` wiped `_identifiedItems = null` in the `finally` block of `sendImageMessage()`, making the "Add items" button silently do nothing. The existing 20 tests all passed — they tested endpoints in isolation but never tested the analyze→add lifecycle as a connected flow.

## Decision

Added `TestImageLifecycle` class (6 tests) that chains the `/chat/image` and `/chat/image/add` endpoints together, verifying:
1. Items returned by analysis are valid input for the add endpoint (format compatibility)
2. Added items actually appear in the items list (DB verification)
3. Empty items list is handled gracefully (catches the wiped-state bug pattern)
4. Single-item and multi-item flows both work end-to-end

## Principle

**Multi-step user workflows must be tested as connected flows, not just individual endpoints.** When the frontend chains two API calls where the output of one feeds into the next, we need at least one test that does the same thing at the API level. This catches contract drift and state-wiping bugs that per-endpoint tests miss.

## Impact

- All 26 image tests pass (was 20)
- Full suite: 307 passed, 1 skipped, 7 deselected
