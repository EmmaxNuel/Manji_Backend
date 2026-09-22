"""
Email templates and utilities for MANJI transactional emails.

Uses Gmail API via apps.core.gmail_service with Django email backend fallback.
"""

from django.conf import settings
from apps.core.gmail_service import send_email_via_gmail, GmailAPIError


def send_email(
    to: str,
    subject: str,
    body_text: str,
    body_html: str = None,
    from_email: str = None,
    reply_to: str = None,
    fail_silently: bool = False,
) -> bool:
    """
    Send email using Gmail API with Django email backend fallback.
    
    Returns True if sent successfully, False if failed and fail_silently=True.
    """
    try:
        send_email_via_gmail(
            to=to,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            from_email=from_email,
            reply_to=reply_to,
            fail_silently=fail_silently,
        )
        return True
    except GmailAPIError:
        if not fail_silently:
            raise
        # Fall back to Django's email backend
        from django.core.mail import send_mail
        send_mail(
            subject=subject,
            message=body_text,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            html_message=body_html,
            fail_silently=fail_silently,
        )
        return True


def send_welcome_email(user) -> bool:
    """Send welcome email to new user."""
    subject = "Welcome to MANJI!"
    body_text = (
        f"Hi {user.username},\n\n"
        f"Welcome to MANJI — the AI-powered creative studio for stories, "
        f"comics, manga, and animation.\n\n"
        f"Get started by creating your first project at "
        f"{settings.FRONTEND_URL}/projects/new\n\n"
        f"Need help? Check out our guide at {settings.FRONTEND_URL}/guide\n\n"
        f"— The MANJI Team"
    )
    body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #ff6b35;">Welcome to MANJI! 🎨</h1>
                <p>Hi {user.username},</p>
                <p>Welcome to MANJI — the AI-powered creative studio for stories, 
                   comics, manga, and animation.</p>
                <p>
                    <a href="{settings.FRONTEND_URL}/projects/new" 
                       style="display: inline-block; padding: 12px 24px; 
                              background: #ff6b35; color: white; 
                              text-decoration: none; border-radius: 4px;">
                        Create Your First Project
                    </a>
                </p>
                <p style="color: #666; font-size: 14px;">
                    Need help? <a href="{settings.FRONTEND_URL}/guide">Check out our guide</a>
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">— The MANJI Team</p>
            </div>
        </body>
        </html>
    """
    return send_email(user.email, subject, body_text, body_html)


def send_password_reset_email(user, reset_link: str) -> bool:
    """Send password reset email."""
    subject = "Reset your MANJI password"
    body_text = (
        f"Hi {user.username},\n\n"
        f"You requested a password reset for your MANJI account.\n\n"
        f"Click the link below to set a new password:\n"
        f"{reset_link}\n\n"
        f"This link expires in 24 hours. If you didn't request this, "
        f"you can safely ignore this email.\n\n"
        f"— The MANJI Team"
    )
    body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #ff6b35;">Reset your MANJI password</h2>
                <p>Hi {user.username},</p>
                <p>You requested a password reset for your MANJI account.</p>
                <p>
                    <a href="{reset_link}" 
                       style="display: inline-block; padding: 12px 24px; 
                              background: #ff6b35; color: white; 
                              text-decoration: none; border-radius: 4px;">
                        Reset Password
                    </a>
                </p>
                <p style="color: #666; font-size: 14px;">
                    This link expires in 24 hours. If you didn't request this, 
                    you can safely ignore this email.
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">— The MANJI Team</p>
            </div>
        </body>
        </html>
    """
    return send_email(user.email, subject, body_text, body_html)


def send_email_verification_email(user, verification_link: str) -> bool:
    """Send email verification email."""
    subject = "Verify your MANJI email address"
    body_text = (
        f"Hi {user.username},\n\n"
        f"Thanks for signing up for MANJI! Please verify your email address.\n\n"
        f"Click the link below to verify:\n"
        f"{verification_link}\n\n"
        f"This link expires in 24 hours.\n\n"
        f"— The MANJI Team"
    )
    body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #ff6b35;">Verify your email address</h2>
                <p>Hi {user.username},</p>
                <p>Thanks for signing up for MANJI! Please verify your email address.</p>
                <p>
                    <a href="{verification_link}" 
                       style="display: inline-block; padding: 12px 24px; 
                              background: #ff6b35; color: white; 
                              text-decoration: none; border-radius: 4px;">
                        Verify Email
                    </a>
                </p>
                <p style="color: #666; font-size: 14px;">
                    This link expires in 24 hours.
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">— The MANJI Team</p>
            </div>
        </body>
        </html>
    """
    return send_email(user.email, subject, body_text, body_html)


def send_new_story_notification_email(recipient_email: str, story_title: str, story_url: str, author_name: str) -> bool:
    """Send notification when a followed user publishes a new story."""
    subject = f"{author_name} published a new story: {story_title}"
    body_text = (
        f"Hi there,\n\n"
        f"{author_name} just published a new story: \"{story_title}\"\n\n"
        f"Read it here: {story_url}\n\n"
        f"— The MANJI Team"
    )
    body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #ff6b35;">New story from {author_name}</h2>
                <p><strong>{story_title}</strong></p>
                <p>
                    <a href="{story_url}" 
                       style="display: inline-block; padding: 12px 24px; 
                              background: #ff6b35; color: white; 
                              text-decoration: none; border-radius: 4px;">
                        Read Now
                    </a>
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">— The MANJI Team</p>
            </div>
        </body>
        </html>
    """
    return send_email(recipient_email, subject, body_text, body_html)


def send_new_episode_notification_email(recipient_email: str, episode_title: str, episode_url: str, series_name: str) -> bool:
    """Send notification when a new official episode is published."""
    subject = f"New episode: {episode_title} ({series_name})"
    body_text = (
        f"Hi there,\n\n"
        f"A new episode is available: \"{episode_title}\" from {series_name}\n\n"
        f"Watch it here: {episode_url}\n\n"
        f"— The MANJI Team"
    )
    body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #ff6b35;">New episode: {series_name}</h2>
                <p><strong>{episode_title}</strong></p>
                <p>
                    <a href="{episode_url}" 
                       style="display: inline-block; padding: 12px 24px; 
                              background: #ff6b35; color: white; 
                              text-decoration: none; border-radius: 4px;">
                        Watch Now
                    </a>
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">— The MANJI Team</p>
            </div>
        </body>
        </html>
    """
    return send_email(recipient_email, subject, body_text, body_html)


def send_comment_notification_email(recipient_email: str, commenter_name: str, content_title: str, content_url: str) -> bool:
    """Send notification when someone comments on user's content."""
    subject = f"{commenter_name} commented on {content_title}"
    body_text = (
        f"Hi there,\n\n"
        f"{commenter_name} left a comment on \"{content_title}\"\n\n"
        f"View it here: {content_url}\n\n"
        f"— The MANJI Team"
    )
    body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #ff6b35;">New comment</h2>
                <p><strong>{commenter_name}</strong> commented on <strong>{content_title}</strong></p>
                <p>
                    <a href="{content_url}" 
                       style="display: inline-block; padding: 12px 24px; 
                              background: #ff6b35; color: white; 
                              text-decoration: none; border-radius: 4px;">
                        View Comment
                    </a>
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">— The MANJI Team</p>
            </div>
        </body>
        </html>
    """
    return send_email(recipient_email, subject, body_text, body_html)