from collections.abc import Callable
from unittest.mock import patch

import pytest

from itemwise import email_service
from itemwise.config import settings


def test_email_url_uses_application_setting() -> None:
    assert email_service.APP_URL == settings.app_url


@pytest.mark.parametrize("send", [email_service.send_invite_email, email_service.send_added_email])
def test_inventory_email_uses_configured_url(send: Callable[[str, str, str], bool], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_service, "APP_URL", "https://itemwise.example")
    with patch.object(email_service, "_send_email", return_value=True) as deliver:
        assert send("recipient@example.com", "inviter@example.com", "Demo inventory")
    html = deliver.call_args.args[2]
    assert 'href="https://itemwise.example"' in html
    assert "azurecontainerapps.io" not in html
