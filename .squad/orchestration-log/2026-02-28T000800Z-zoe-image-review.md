# Orchestration: Zoe — Test Review (feat/image-analysis)

**Date:** 2026-02-28T00:08:00Z  
**Agent:** Zoe (Test Lead)  
**Task:** Test coverage review of image analysis endpoints  
**Verdict:** REQUEST CHANGES

## Summary

Reviewed `tests/test_image_analysis.py` (15 tests). Tests pass and cover happy paths, but critical edge cases and failure modes are untested.

## What's Good

✅ Core functionality tested (analyze_image, /chat/image, /chat/image/add)  
✅ Mock patterns correct (patch at call sites)  
✅ Fixture usage proper (autouse limiter reset, async fixtures, DB mocking)  
✅ `test_config.py` URL-encoding assertion updated correctly

## Missing Tests — REQUEST CHANGES

### 1. File Size Limit (10 MB) — REQUIRED
**Issue:** No test verifies `len(image_data) > MAX_IMAGE_SIZE` validation  
**Risk:** Regression allows DoS via huge uploads  
**Test:** Upload 10 MB + 1 byte, assert HTTP 400 "too large"

### 2. Rate Limiting Behavior — RECOMMENDED
**Issue:** `/chat/image` has 5/minute limit but no test hits the 6th request  
**Risk:** Rate limit might not work as expected  
**Test:** Loop 6 image uploads <60s, assert 6th returns HTTP 429

### 3. Vision API Network Errors — RECOMMENDED
**Issue:** No test for `analyze_image()` raising exceptions (timeout, API error)  
**Risk:** Unhandled exceptions could crash endpoint  
**Test:** Mock `get_client().chat.completions.create()` to raise `openai.APIError`, verify error response (not 500)

### 4. Concurrent Upload Handling — RECOMMENDED
**Issue:** No test for simultaneous uploads by same user  
**Risk:** Race conditions in DB or file handling  
**Test:** Use `asyncio.gather()` to POST 3 images concurrently, verify all succeed

### 5. E2E Test for Image Upload — RECOMMENDED
**Issue:** No browser-based test for full upload flow (file input → FormData → response rendering)  
**Risk:** Frontend-backend integration untested  
**Test:** Add to `test_e2e.py` with in-memory PNG, file input, assertion on rendered results

## Quality Observations

✅ Assertions are meaningful  
✅ Fixtures properly scoped  
⚠️ Some tests overlap (consolidate or clarify)

## Verdict

**REQUEST CHANGES** — Add missing tests:
1. File size limit breach (REQUIRED)
2. Rate limit enforcement (RECOMMENDED)
3. Vision API errors (RECOMMENDED)
4. Concurrent uploads (RECOMMENDED)
5. E2E browser upload (RECOMMENDED)

After adding tests, run full suite + E2E, then request re-review.
