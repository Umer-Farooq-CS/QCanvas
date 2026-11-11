"""Email delivery helpers for authentication OTP flows."""
from dataclasses import dataclass
from typing import Optional
import httpx

from app.config.settings import settings


@dataclass
class EmailSendResult:
    success: bool
    provider: str
    message_id: Optional[str] = None
    error: Optional[str] = None


class EmailService:
    """Minimal provider wrapper for transactional OTP emails."""

    FALLBACK_MASTER_ADMIN_EMAIL = "muhammadirtazakhan2004@gmail.com"

    @staticmethod
    def _sender() -> str:
        return f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"

    @staticmethod
    def send_signup_otp(email: str, otp: str, expires_minutes: int) -> EmailSendResult:
        subject = "Verify your QCanvas account"
        html = (
            "<p>Your QCanvas verification code is:</p>"
            f"<h2 style='letter-spacing:4px'>{otp}</h2>"
            f"<p>This code expires in {expires_minutes} minutes.</p>"
            "<p>If you did not create this account, you can ignore this email.</p>"
        )
        return EmailService._send_email(email=email, subject=subject, html=html)

    @staticmethod
    def send_password_reset_otp(email: str, otp: str, expires_minutes: int) -> EmailSendResult:
        subject = "Your QCanvas password reset code"
        html = (
            "<p>You requested a password reset for your QCanvas account.</p>"
            f"<h2 style='letter-spacing:4px'>{otp}</h2>"
            f"<p>This code expires in {expires_minutes} minutes.</p>"
            "<p>If you did not request this reset, ignore this email.</p>"
        )
        return EmailService._send_email(email=email, subject=subject, html=html)

    @staticmethod
    def send_admin_approval_request(full_name: str, username: str, email: str, approval_link: str) -> EmailSendResult:
        recipient = (settings.MASTER_ADMIN_EMAIL or "").strip() or EmailService.FALLBACK_MASTER_ADMIN_EMAIL

        subject = "QCanvas admin approval request"
        html = (
            "<p>An admin access request was submitted on QCanvas.</p>"
            "<p><strong>Applicant details:</strong></p>"
            f"<ul><li>Full Name: {full_name}</li><li>Username: {username}</li><li>Email: {email}</li></ul>"
            "<p>Review and approve the request using the secure link below:</p>"
            f"<p><a href='{approval_link}' style='display:inline-block;padding:12px 18px;background:#4f46e5;color:#ffffff;text-decoration:none;border-radius:8px'>Review Admin Access Request</a></p>"
            f"<p>Or open this link manually:</p><p><a href='{approval_link}'>{approval_link}</a></p>"
            "<p>If you did not expect this request, you can ignore this email.</p>"
        )
        return EmailService._send_email(
            email=recipient,
            subject=subject,
            html=html,
        )

    @staticmethod
    def send_admin_approved_notification(full_name: str, username: str, email: str) -> EmailSendResult:
        subject = "Your QCanvas admin request was approved"
        html = (
            f"<p>Hi {full_name},</p>"
            "<p>Congratulations! Your request to become a QCanvas admin has been approved by the master admin.</p>"
            "<p>You can now sign in and access admin features.</p>"
            "<p><strong>Your account details:</strong></p>"
            f"<ul><li>Username: {username}</li><li>Email: {email}</li></ul>"
            "<p><strong>Current admin benefits:</strong></p>"
            "<ul><li>Access to the Cirq RAG Code Assistant</li></ul>"
            "<p>Welcome aboard,<br/>QCanvas Team</p>"
        )
        return EmailService._send_email(email=email, subject=subject, html=html)

    @staticmethod
    def _send_email(email: str, subject: str, html: str) -> EmailSendResult:
        provider = settings.EMAIL_PROVIDER.lower()

        if provider == "resend":
            return EmailService._send_via_resend(email=email, subject=subject, html=html)

        return EmailSendResult(success=False, provider=provider, error=f"Unsupported email provider: {provider}")

    @staticmethod
    def _send_via_resend(email: str, subject: str, html: str) -> EmailSendResult:
        if not settings.RESEND_API_KEY:
            # Keep local development friction low if key is not configured yet.
            print(f"[EmailService] RESEND_API_KEY missing, skipping delivery to {email}")
            return EmailSendResult(success=True, provider="resend", message_id="dev-noop")

        payload = {
            "from": EmailService._sender(),
            "to": [email],
            "subject": subject,
            "html": html,
        }
        headers = {
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(f"{settings.RESEND_API_BASE_URL}/emails", json=payload, headers=headers)

            if response.status_code >= 400:
                return EmailSendResult(
                    success=False,
                    provider="resend",
                    error=f"Resend returned {response.status_code}: {response.text}",
                )

            data = response.json()
            return EmailSendResult(
                success=True,
                provider="resend",
                message_id=data.get("id"),
            )
        except Exception as exc:
            return EmailSendResult(success=False, provider="resend", error=str(exc))
