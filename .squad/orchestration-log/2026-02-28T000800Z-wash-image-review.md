# Orchestration: Wash — Frontend Review (feat/image-analysis)

**Date:** 2026-02-28T00:08:00Z  
**Agent:** Wash (Frontend Developer)  
**Task:** Frontend UI review of image upload feature  
**Verdict:** REQUEST CHANGES

## Critical Issues

### 1. Inconsistent Error Handling
**Issue:** `sendImageMessage()` and `addImageItems()` don't use `showConnectionError()` utility  
**Fix:** Replace inline errors with `showConnectionError(e)` to match app pattern

### 2. Truncated SVG Path
**Issue:** Line 91 in `chat.js` has `<path stroke-li` (should be `stroke-linecap`)  
**Fix:** Complete the SVG markup for send button icon

### 3. Accessibility Gaps
**Issues:**
- Camera button has `title` but no `aria-label`
- Clear preview X button has no text alternative

**Fix:** Add `aria-label` attributes to both buttons

### 4. File Size Contract Unclear
**Issue:** Frontend validates 10 MB but backend limit not coordinated  
**Fix:** Document limit in code comments or validate backend errors

## Strengths

✅ Core implementation solid (state management, FormData, mobile support)  
✅ Good file input UX patterns

## Action Items

1. Fix SVG path truncation
2. Add aria-labels
3. Integrate `showConnectionError()` utility
4. Clarify file size contract
