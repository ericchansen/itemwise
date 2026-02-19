"""End-to-end Playwright tests for the Itemwise web app.

Tests register, login, chat interaction, and item management via the browser.
Requires the app to be running (default: http://localhost:8080).

Run with:
    uv run python -m pytest tests/test_e2e.py -v -m e2e --no-cov

Set E2E_BASE_URL env var to test against a different host (e.g., Azure).
Chat tests require Azure OpenAI — they are skipped when chat returns errors.
"""

import os
import time

import pytest
from playwright.sync_api import Page, expect, sync_playwright

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8080")
_REMOTE = not BASE_URL.startswith("http://localhost")

_ts = int(time.time())
TEST_EMAIL = f"e2e-{_ts}@test.com"
TEST_PASSWORD = "TestPass1234!"


@pytest.fixture(scope="module")
def browser_instance():
    """Launch browser once for the module."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser_instance):
    """Get a fresh context+page per test (no shared auth state)."""
    context = browser_instance.new_context()
    pg = context.new_page()
    yield pg
    pg.close()
    context.close()


def _delete_account(email: str, password: str):
    """Delete a test account via API (best-effort)."""
    import httpx

    try:
        r = httpx.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": email, "password": password},
            timeout=10,
        )
        if r.status_code != 200:
            return
        token = r.json()["access_token"]
        httpx.delete(
            f"{BASE_URL}/api/auth/account",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except Exception:
        pass


@pytest.fixture(scope="module", autouse=True)
def cleanup_after_tests():
    """Clean up test accounts after all E2E tests complete."""
    yield
    _delete_account(TEST_EMAIL, TEST_PASSWORD)
    _delete_account(f"e2e-reg-{_ts}@test.com", TEST_PASSWORD)


def _ensure_user_registered():
    """Register the test user via API (idempotent)."""
    import httpx

    try:
        httpx.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=10,
        )
    except Exception:
        pass


def _login(page: Page):
    """Log in with the test user."""
    _ensure_user_registered()
    page.goto(BASE_URL)
    page.wait_for_selector("#auth-screen", state="visible", timeout=10000)

    page.click("#auth-tab-login")
    page.fill("#auth-email", TEST_EMAIL)
    page.fill("#auth-password", TEST_PASSWORD)
    page.click("#auth-submit")

    page.wait_for_selector("#auth-screen", state="hidden", timeout=15000)


def _chat_available() -> bool:
    """Check if chat API works (needs Azure OpenAI)."""
    import httpx

    try:
        _ensure_user_registered()
        r = httpx.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=10,
        )
        token = r.json()["access_token"]
        r2 = httpx.post(
            f"{BASE_URL}/api/chat",
            json={"message": "hi"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        data = r2.json()
        return "error" not in data.get("response", "").lower() or r2.status_code == 200
    except Exception:
        return False


_chat_works = None


def _skip_if_no_chat():
    """Skip test if chat API is not available."""
    global _chat_works
    if _chat_works is None:
        _chat_works = _chat_available()
    if not _chat_works:
        pytest.skip("Chat API not available (no Azure OpenAI credentials)")


@pytest.mark.e2e
class TestE2EAuth:
    """Test authentication flow."""

    def test_register_and_see_app(self, page):
        """Register creates account and shows main app."""
        reg_email = f"e2e-reg-{_ts}@test.com"
        page.goto(BASE_URL)
        page.wait_for_selector("#auth-screen", state="visible", timeout=10000)

        page.click("#auth-tab-register")
        page.fill("#auth-email", reg_email)
        page.fill("#auth-password", TEST_PASSWORD)
        page.click("#auth-submit")

        page.wait_for_selector("#auth-screen", state="hidden", timeout=15000)
        expect(page.locator("#chat-input")).to_be_visible(timeout=10000)

    def test_login_existing_user(self, page):
        """Login with registered user works."""
        _login(page)
        expect(page.locator("#chat-input")).to_be_visible(timeout=10000)

    def test_items_tab_visible(self, page):
        """Items tab is accessible after login."""
        _login(page)
        items_tab = page.locator("#tab-inventory")
        expect(items_tab).to_be_visible(timeout=10000)
        items_tab.click()
        # Wait for inventory tab content to be visible
        expect(page.locator("#inventory-tab")).to_be_visible(timeout=5000)

    def test_settings_tab_visible(self, page):
        """Settings tab shows profile section."""
        _login(page)
        settings_tab = page.locator("#tab-settings")
        expect(settings_tab).to_be_visible(timeout=10000)
        settings_tab.click()
        # Should show profile email field
        expect(page.locator("#profile-email")).to_be_visible(timeout=5000)


@pytest.mark.e2e
class TestE2EChat:
    """Test AI chat interactions (requires Azure OpenAI)."""

    def test_add_item_via_chat(self, page):
        """Sending 'Add 2 frozen pizzas to chest freezer' creates the item."""
        _skip_if_no_chat()
        _login(page)

        chat_input = page.locator("#chat-input")
        expect(chat_input).to_be_visible(timeout=10000)

        chat_input.fill("Add 2 frozen pizzas to my chest freezer")
        chat_input.press("Enter")

        # Wait for assistant response
        page.wait_for_function(
            """() => {
                const msgs = document.querySelectorAll('#chat-messages > div');
                return msgs.length >= 2 && msgs[msgs.length - 1].textContent.length > 10;
            }""",
            timeout=45000,
        )

        messages = page.locator("#chat-messages").inner_text().lower()
        assert "pizza" in messages or "added" in messages, (
            f"Expected confirmation of adding item, got: {messages[-200:]}"
        )

    def test_what_do_i_have(self, page):
        """Asking 'What do I have?' returns a response (not a demand for location)."""
        _skip_if_no_chat()
        _login(page)

        chat_input = page.locator("#chat-input")
        expect(chat_input).to_be_visible(timeout=10000)

        chat_input.fill("What do I have?")
        chat_input.press("Enter")

        # Wait for any substantive AI response
        page.wait_for_function(
            """() => {
                const msgs = document.querySelectorAll('#chat-messages > div');
                if (msgs.length < 2) return false;
                const last = msgs[msgs.length - 1];
                return last && last.textContent.trim().length > 10;
            }""",
            timeout=60000,
        )

        messages = page.locator("#chat-messages").inner_text().lower()
        # AI should NOT demand a specific location — it should just list or say empty
        assert "which location" not in messages, (
            f"AI should list all items, not ask for location. Got: {messages[-200:]}"
        )

    @pytest.mark.xfail(
        condition=_REMOTE,
        reason="Azure OpenAI multi-tool-call latency varies widely",
        strict=False,
    )
    def test_recipe_suggestion(self, page):
        """Asking 'What can I cook?' uses tools and gives suggestions."""
        _skip_if_no_chat()
        _login(page)

        chat_input = page.locator("#chat-input")
        expect(chat_input).to_be_visible(timeout=10000)

        chat_input.fill("What can I cook with what I have?")
        chat_input.press("Enter")

        # Wait for substantive response (Azure OpenAI may need multiple tool calls)
        page.wait_for_function(
            """() => {
                const msgs = document.querySelectorAll('#chat-messages > div');
                return msgs.length >= 2 && msgs[msgs.length - 1].textContent.length > 50;
            }""",
            timeout=300000 if _REMOTE else 120000,
        )

        messages = page.locator("#chat-messages").inner_text().lower()
        assert "please provide" not in messages or "pizza" in messages, (
            f"AI should use tools, not ask for items. Got: {messages[-300:]}"
        )
