"""
Gmail API email service for sending transactional emails.

Uses OAuth2 with refresh token for server-to-server authentication.
Falls back to Django's default email backend if not configured.
"""

import base64
import json
import os
from email.message import EmailMessage
from typing import Optional

import requests
from django.conf import settings


class GmailAPIError(Exception):
    """Raised when Gmail API request fails."""
    pass


class GmailEmailService:
    """
    Service for sending emails via Gmail API.
    
    Requires:
    - GOOGLE_OAUTH_CLIENT_ID
    - GOOGLE_OAUTH_CLIENT_SECRET  
    - GOOGLE_OAUTH_REFRESH_TOKEN
    
    Get these from Google Cloud Console:
    1. Create OAuth 2.0 Client ID (Web application)
    2. Authorized redirect URI: https://developers.google.com/oauthplayground
    3. Use OAuth Playground to get refresh token with scope:
       https://www.googleapis.com/auth/gmail.send
    """
    
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
    
    def __init__(self):
        self.client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
        self.client_secret = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "")
        self.refresh_token = getattr(settings, "GOOGLE_OAUTH_REFRESH_TOKEN", "")
        self._access_token: Optional[str] = None
        self._token_expiry = 0
    
    def is_configured(self) -> bool:
        """Check if all required credentials are set."""
        return bool(self.client_id and self.client_secret and self.refresh_token)
    
    def _get_access_token(self) -> str:
        """Get valid access token, refreshing if necessary."""
        import time
        
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token
        
        if not self.is_configured():
            raise GmailAPIError("Gmail API not configured. Set GOOGLE_OAUTH_CLIENT_ID, "
                              "GOOGLE_OAUTH_CLIENT_SECRET, and GOOGLE_OAUTH_REFRESH_TOKEN.")
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }
        
        response = requests.post(self.TOKEN_URL, data=data, timeout=30)
        
        if response.status_code != 200:
            raise GmailAPIError(f"Failed to refresh access token: {response.text}")
        
        token_data = response.json()
        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        self._token_expiry = time.time() + expires_in
        
        return self._access_token
    
    def _build_raw_message(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> str:
        """Build RFC 2822 raw message for Gmail API."""
        
        msg = EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject
        msg["From"] = from_email or settings.DEFAULT_FROM_EMAIL
        
        if reply_to:
            msg["Reply-To"] = reply_to
        
        if body_html:
            msg.set_content(body_text)
            msg.add_alternative(body_html, subtype="html")
        else:
            msg.set_content(body_text)
        
        # Gmail API requires base64url encoding (no padding)
        raw_bytes = msg.as_bytes()
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode()
        return raw_b64.rstrip("=")
    
    def send_email(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> dict:
        """
        Send email via Gmail API.
        
        Returns dict with message ID and thread ID on success.
        Raises GmailAPIError on failure.
        """
        access_token = self._get_access_token()
        
        raw_message = self._build_raw_message(
            to=to,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            from_email=from_email,
            reply_to=reply_to,
        )
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        
        payload = {"raw": raw_message}
        
        response = requests.post(
            self.GMAIL_SEND_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        
        if response.status_code != 200:
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json.get("error", {}).get("message", error_detail)
            except Exception:
                pass
            raise GmailAPIError(f"Gmail API send failed ({response.status_code}): {error_detail}")
        
        return response.json()


# Singleton instance
gmail_service = GmailEmailService()


def send_email_via_gmail(
    to: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    from_email: Optional[str] = None,
    reply_to: Optional[str] = None,
    fail_silently: bool = False,
) -> bool:
    """
    Convenience function matching Django's send_mail signature.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body_text: Plain text body
        body_html: Optional HTML body
        from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)
        reply_to: Optional reply-to address
        fail_silently: If True, log errors instead of raising
    
    Returns:
        True if sent successfully, False if failed and fail_silently=True
    
    Raises:
        GmailAPIError if fail_silently=False and send fails
    """
    try:
        gmail_service.send_email(
            to=to,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            from_email=from_email,
            reply_to=reply_to,
        )
        return True
    except GmailAPIError as exc:
        if not fail_silently:
            raise
        # Log error in production
        import logging
        logging.getLogger(__name__).error(f"Gmail send failed: {exc}")
        return False