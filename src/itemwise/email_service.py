"""Email service for sending invite and notification emails via Azure Communication Services."""

import logging
from azure.communication.email import EmailClient
from .config import settings

logger = logging.getLogger(__name__)

_email_client = None

APP_URL = "https://ca-api-ki7zeahtw2lr6.proudwater-caeb734c.centralus.azurecontainerapps.io"


def _get_email_client() -> EmailClient | None:
    """Get or create the email client singleton."""
    global _email_client
    if _email_client is not None:
        return _email_client
    conn_str = settings.azure_communication_connection_string
    if not conn_str:
        logger.warning("AZURE_COMMUNICATION_CONNECTION_STRING not set — emails disabled")
        return None
    _email_client = EmailClient.from_connection_string(conn_str)
    return _email_client


def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email. Returns True on success, False on failure. Non-blocking best-effort."""
    sender = settings.azure_communication_sender
    if not sender:
        logger.warning("AZURE_COMMUNICATION_SENDER not set — cannot send email")
        return False
    client = _get_email_client()
    if client is None:
        return False
    try:
        message = {
            "senderAddress": sender,
            "recipients": {"to": [{"address": to_email}]},
            "content": {"subject": subject, "html": html_body},
        }
        poller = client.begin_send(message)
        result = poller.result()
        logger.info("Email sent to %s, status=%s", to_email, result.get("status"))
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def send_invite_email(to_email: str, inviter_email: str, inventory_name: str) -> bool:
    """Send a signup invitation email to a non-registered user."""
    subject = "You're invited to share an inventory on Itemwise"
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 32px; background: #0f0f0f; color: #ffffff; border-radius: 16px;">
        <h1 style="font-size: 24px; margin: 0 0 24px 0;">📦 Itemwise</h1>
        <p style="color: #cccccc; line-height: 1.6;">
            <strong>{inviter_email}</strong> has invited you to share their inventory
            <strong>"{inventory_name}"</strong> on Itemwise.
        </p>
        <p style="color: #cccccc; line-height: 1.6;">
            Itemwise is an AI-powered inventory manager. Create an account to get started:
        </p>
        <a href="{APP_URL}" style="display: inline-block; margin: 16px 0; padding: 12px 24px; background: #3b82f6; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600;">
            Sign Up on Itemwise
        </a>
        <p style="color: #666666; font-size: 12px; margin-top: 24px;">
            Once you've created an account with this email address ({to_email}),
            ask {inviter_email} to add you again and you'll automatically join their inventory.
        </p>
    </div>
    """
    return _send_email(to_email, subject, html_body)


def send_added_email(to_email: str, inviter_email: str, inventory_name: str) -> bool:
    """Send a notification email to a user who was added to an inventory."""
    subject = "You've been added to an inventory on Itemwise"
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 32px; background: #0f0f0f; color: #ffffff; border-radius: 16px;">
        <h1 style="font-size: 24px; margin: 0 0 24px 0;">📦 Itemwise</h1>
        <p style="color: #cccccc; line-height: 1.6;">
            <strong>{inviter_email}</strong> has added you to their inventory
            <strong>"{inventory_name}"</strong> on Itemwise.
        </p>
        <p style="color: #cccccc; line-height: 1.6;">
            You can now view and manage shared items in this inventory.
        </p>
        <a href="{APP_URL}" style="display: inline-block; margin: 16px 0; padding: 12px 24px; background: #3b82f6; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600;">
            Open Itemwise
        </a>
    </div>
    """
    return _send_email(to_email, subject, html_body)
