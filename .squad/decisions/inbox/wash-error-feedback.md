# Decision: Frontend Connection Error Feedback Pattern

**Author:** Wash (Frontend Dev)
**Date:** 2026-02-27
**Status:** Implemented

## Context
When Azure PostgreSQL auto-stops, all API endpoints fail but the frontend silently swallows errors — users see buttons that "do nothing" with zero feedback.

## Decision
Added a shared `showConnectionError(error)` utility in `utils.js` that shows a fixed-position dismissible banner via the existing `showAlert` pattern. All previously silent catch blocks in `items.js` and `settings.js` now call this utility. `chat.js` was already handling errors properly.

## Key Pattern
- Network errors (TypeError) → "⚠️ Can't connect to server. Please try again later."
- Other errors → "⚠️ Something went wrong. Please try again later."
- `Unauthorized` errors are filtered out (handled by auth flow/logout).
- The banner element is `#connection-error` in `index.html`, reused by all modules.

## Files Changed
- `frontend/js/utils.js` — added `showConnectionError()`
- `frontend/js/items.js` — 4 catch blocks fixed
- `frontend/js/settings.js` — 3 catch blocks fixed
- `frontend/index.html` — added `#connection-error` banner element
