# Image Analysis Bug — Diagnosis Report

**Author:** Kaylee (Backend Dev)
**Date:** 2026-03-02
**Status:** Investigation complete — awaiting fix

## Symptom

Uploading a photo to the `/api/v1/chat/image` endpoint returns:
> "I had trouble analyzing that image. Try a clearer photo or describe the items instead."

This is the catch-all error message from `api.py`'s `chat_image` endpoint, meaning the `analyze_image()` call in `ai_client.py` is throwing an exception.

## Root Cause (High Confidence)

**The `gpt-4o` vision model deployment does not exist in Azure OpenAI.**

### Evidence

1. **Master's `infra/resources.bicep`** only deploys two models:
   - `gpt-4o-mini` (chat deployment)
   - `text-embedding-3-small` (embedding deployment)
   - **No vision-capable deployment exists.**

2. **The feature branch's Bicep** (`origin/feat/image-analysis`) adds a third deployment:
   ```bicep
   resource visionDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
     parent: openAi
     name: azureOpenAiVisionDeployment  // defaults to 'gpt-4o'
     sku: { name: 'GlobalStandard', capacity: 10 }
     properties: { model: { format: 'OpenAI', name: 'gpt-4o', version: '2024-08-06' } }
   }
   ```
   It also adds the `AZURE_OPENAI_VISION_DEPLOYMENT` env var to the Container App config.

3. **But this Bicep was never provisioned.** The feature was deployed with `azd deploy` (code only), not `azd provision` (infrastructure). So:
   - The `gpt-4o` model deployment was never created in Azure OpenAI
   - The `AZURE_OPENAI_VISION_DEPLOYMENT` env var was never added to the Container App

4. **The code falls back gracefully but to a non-existent deployment:**
   ```python
   deployment = os.getenv("AZURE_OPENAI_VISION_DEPLOYMENT", "gpt-4o")
   ```
   Since the env var isn't set, it uses `"gpt-4o"` — but that deployment doesn't exist. The Azure OpenAI SDK throws a `NotFoundError` (or similar), which is caught by the broad `except Exception` block.

## Secondary Issue: Synchronous Blocking Call

`analyze_image()` in `ai_client.py` is a **synchronous** function that uses the synchronous `AzureOpenAI` client. It's called from an `async` FastAPI endpoint without `asyncio.to_thread()`:

```python
# In api.py (async endpoint):
items = analyze_image(image_data, content_type, user_hint=message)  # BLOCKS event loop
```

This won't cause the error message, but it **blocks the entire event loop** during the OpenAI API call (which could take 5-10 seconds for vision). Under load, this would make the entire app unresponsive.

## Code Flow Summary

1. **Frontend** (`chat.js`): Sends image as `FormData` (multipart) to `POST /api/v1/chat/image`
2. **Backend** (`api.py`): Validates image type/size/magic bytes, then calls `analyze_image()`
3. **AI Client** (`ai_client.py`): Base64-encodes image, sends to Azure OpenAI `gpt-4o` deployment
4. **Azure OpenAI**: Returns `404 / DeploymentNotFound` because `gpt-4o` deployment doesn't exist
5. **Backend**: Catches exception, returns "I had trouble analyzing that image..."

## Fix Required

### Must-do (fixes the bug):
1. Run `azd provision` to deploy the updated Bicep (creates the `gpt-4o` deployment and sets the env var)
   — OR —
   Manually create the `gpt-4o` deployment in Azure OpenAI and set the env var on the Container App

### Should-do (prevents event loop blocking):
2. Wrap the synchronous `analyze_image()` call in `asyncio.to_thread()`:
   ```python
   items = await asyncio.to_thread(analyze_image, image_data, content_type, user_hint=message)
   ```
   — OR — Convert `analyze_image()` to use the async `AsyncAzureOpenAI` client.

### Nice-to-have (better debugging):
3. The `except Exception` is too broad. Log the specific exception type so we can distinguish between deployment-not-found, auth errors, rate limits, and actual image processing failures. The `logger.exception()` already logs it, but the user gets no clue what went wrong.

## Files Involved

| File | Branch | What needs to change |
|------|--------|---------------------|
| `infra/resources.bicep` | `feat/image-analysis` | Already has vision deployment — just needs `azd provision` |
| `infra/main.bicep` | `feat/image-analysis` | Already has `azureOpenAiVisionDeployment` param |
| `src/itemwise/api.py` | `feat/image-analysis` | Wrap `analyze_image()` in `asyncio.to_thread()` |
| `src/itemwise/ai_client.py` | `feat/image-analysis` | No changes needed (code is correct) |
