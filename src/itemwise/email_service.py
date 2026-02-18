"""Email service for sending invite and notification emails via Azure Communication Services."""

import logging
from azure.communication.email import EmailClient
from azure.core.exceptions import AzureError
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
    except (AzureError, ValueError):
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


def send_password_reset_email(to_email: str, reset_token: str, app_url: str) -> bool:
    """Send a password reset email with a link containing the reset token."""
    reset_link = f"{app_url}?reset_token={reset_token}"
    subject = "Reset your Itemwise password"
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 32px; background: #0f0f0f; color: #ffffff; border-radius: 16px;">
        <h1 style="font-size: 24px; margin: 0 0 24px 0;">📦 Itemwise</h1>
        <p style="color: #cccccc; line-height: 1.6;">
            We received a request to reset your password. Click the button below to set a new password:
        </p>
        <a href="{reset_link}" style="display: inline-block; margin: 16px 0; padding: 12px 24px; background: #3b82f6; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600;">
            Reset Password
        </a>
        <p style="color: #666666; font-size: 12px; margin-top: 24px;">
            This link expires in 15 minutes. If you didn't request a password reset, you can safely ignore this email.
        </p>
    </div>
    """
    return _send_email(to_email, subject, html_body)


def send_expiration_digest_email(to_email: str, expiring_items: list, app_url: str) -> bool:
    """Send an email digest listing items that are expiring soon."""
    if not expiring_items:
        return False

    # Group items by days_until_expiry
    groups: dict[str, list] = {}
    for item in expiring_items:
        days = item.get("days_until_expiry", 0)
        if days <= 0:
            label = "Already expired"
        elif days == 1:
            label = "Expires tomorrow"
        else:
            label = f"Expires in {days} days"
        groups.setdefault(label, []).append(item)

    # Build HTML rows grouped by urgency
    sections_html = ""
    for label, items in groups.items():
        rows = ""
        for it in items:
            loc = it.get("location_name") or "—"
            rows += (
                f'<tr><td style="padding:6px 12px;border-bottom:1px solid #333;">{it["item_name"]}</td>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #333;">{it["lot_quantity"]}</td>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #333;">{loc}</td>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #333;">{it["expiration_date"]}</td></tr>'
            )
        sections_html += f"""
        <h3 style="color:#f59e0b;margin:16px 0 8px 0;font-size:14px;">⚠️ {label}</h3>
        <table style="width:100%;border-collapse:collapse;color:#cccccc;font-size:13px;">
            <tr style="text-align:left;color:#888;">
                <th style="padding:6px 12px;border-bottom:1px solid #444;">Item</th>
                <th style="padding:6px 12px;border-bottom:1px solid #444;">Qty</th>
                <th style="padding:6px 12px;border-bottom:1px solid #444;">Location</th>
                <th style="padding:6px 12px;border-bottom:1px solid #444;">Expires</th>
            </tr>
            {rows}
        </table>
        """

    subject = f"Itemwise: {len(expiring_items)} item(s) expiring soon"
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 32px; background: #0f0f0f; color: #ffffff; border-radius: 16px;">
        <h1 style="font-size: 24px; margin: 0 0 24px 0;">📦 Itemwise — Expiration Report</h1>
        <p style="color: #cccccc; line-height: 1.6;">
            You have <strong>{len(expiring_items)}</strong> item(s) expiring soon. Review them below:
        </p>
        {sections_html}
        <a href="{app_url}" style="display: inline-block; margin: 24px 0 0 0; padding: 12px 24px; background: #3b82f6; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600;">
            Open Itemwise
        </a>
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
