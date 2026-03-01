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

### Image Upload Feature Review (feat/image-analysis branch)
**Reviewed:** 2026-02-28

**VERDICT: REQUEST CHANGES**

**Critical Issues:**
1. **Missing Network Error Handling in `sendImageMessage()`** — Upload to `/api/v1/chat/image` only catches `Unauthorized` and shows "Connection error" for everything else, but doesn't use `showConnectionError()` utility like the rest of the app. This breaks the established error pattern (connection banner at top of page).
2. **Missing Network Error Handling in `addImageItems()`** — Same issue when POSTing to `/api/v1/chat/image/add`.
3. **No Max File Size Feedback Before Upload** — Frontend checks 10 MB limit but doesn't tell the backend. If backend has a different limit (e.g., 5 MB or 20 MB), user gets a generic error. Should either document this contract or validate server-side response.
4. **Truncated SVG in sendBtn Restoration** — Line 91 in diff shows `<path stroke-li` (truncated) — this will break the send button icon after image upload completes.

**Accessibility Issues:**
5. **Missing `alt` text on user-uploaded image** — The preview shows `alt="Uploaded"` but the semantic preview in chat has no alt text (line 59 shows `alt="Uploaded"`... wait, it does have alt text on line 59). Actually this is OK.
6. **Camera button has `title` but no `aria-label`** — Screen readers may not announce "Upload image" consistently. Add `aria-label="Upload image"`.
7. **Clear preview button has no text alternative** — The X button (lines 171-173 in index.html) has an SVG but no aria-label or sr-only text.

**UX Issues:**
8. **Image preview dismiss not obvious** — Small X button in corner is easy to miss. Consider adding text like "Remove" or making the button larger/more obvious.
9. **"Skip" button in add prompt is ambiguous** — Does "Skip" mean "don't add items" or "cancel the whole operation"? The code calls `dismissImagePrompt()` which shows "No items added." — this is correct but the label could be clearer (e.g., "Don't add" or "Cancel").
10. **No loading state for image preview** — FileReader.onload could take time for large images. Consider showing a loading spinner or skeleton while the preview renders.
11. **Input padding change is too subtle** — `px-4` → `px-12` gives room for camera button, but this shifts text noticeably when toggling between states. Consider keeping consistent padding or using absolute positioning differently.

**Good Patterns:**
- Uses `_pendingImage` module-scoped state to track selection (clean)
- Properly clears state in `clearImagePreview()`
- Exposes functions to global scope for onclick handlers (matches existing pattern)
- Uses `authFetch` for authenticated requests (correct)
- Disables buttons during async operations (good UX)
- Uses FormData for multipart upload (correct for image files)
- `capture="environment"` for mobile rear camera (excellent mobile UX)
- File type restrictions are appropriate (jpeg, png, webp, gif)
- Max 10 MB client-side validation before upload (prevents wasted bandwidth)

**Recommendations:**
1. Wrap all fetch calls in try/catch using `showConnectionError(error)` from utils.js
2. Fix truncated SVG path in line 91 (`stroke-linecap` not `stroke-li`)
3. Add `aria-label="Upload image"` to camera button
4. Add `aria-label="Remove image"` to clear preview button
5. Change "Skip" button text to "Don't add" for clarity
6. Consider adding loading state for FileReader preview
7. Test on mobile devices with actual camera capture
8. Ensure backend validates file size and returns clear error message
