# Wash — History

## Project Context
- **Project:** Itemwise — conversational inventory assistant
- **Stack:** Python, FastAPI, PostgreSQL, vanilla JS, Azure Container Apps, OpenAI
- **User:** Eric Hansen

## Learnings
- `showAlert(el, msg)` in `utils.js` is the standard pattern for dismissible banners — takes a DOM element and message string, auto-dismisses after 8s.
- `authFetch()` in `auth.js` throws `Error('Unauthorized')` on 401 — all error handlers must filter this out (it triggers logout, not a connection error).
- `chat.js` already had proper error feedback (`addMessage('Connection error. Try again.')`) — no changes needed there.
- `settings.js` `handleChangePassword`, `handleAddMember`, `handleSendExpirationReport` already had inline error feedback — only `loadInventories`, `loadProfile`, `loadMembers` were silently swallowing.
- Global error banner lives at `<div id="connection-error">` at the top of `<body>` in `index.html`, used by `showConnectionError()` in `utils.js`.
- TypeError from fetch = network unreachable; other errors = generic "something went wrong".
