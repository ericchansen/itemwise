# Orchestration: Kaylee — Backend Review (feat/image-analysis)

**Date:** 2026-02-28T00:08:00Z  
**Agent:** Kaylee (Backend Developer)  
**Task:** Backend API review of image analysis endpoints  
**Verdict:** REQUEST CHANGES

## Critical Issues

### 1. DetachedInstanceError in `chat_image_add_items()`
- **Location:** `src/itemwise/api.py:1743-1776`
- **Problem:** `loc` object accessed outside session scope after loop completes
- **Fix:** Move response construction inside session context before returning

### 2. Missing error handling in bulk add loop
- **Location:** `src/itemwise/api.py:1743-1774`
- **Problem:** No try-catch around `create_item()` / `create_lot()` calls; partial failures silent
- **Fix:** Wrap loop in try-catch, track successes and failures, return both in response

## Strengths

✅ Vision API integration solid (Base64, JSON parsing, markdown handling)  
✅ File validation correct and in right order  
✅ Rate limits reasonable (5/min vision, 10/min bulk add)  
✅ Follows existing patterns (`get_or_create_location`, `generate_display_name`)  
✅ Prompt engineering is clear and graceful

## Action Items

1. Fix DetachedInstanceError
2. Add error handling with failure tracking
3. Test edge cases (partial failures, session closure)
