"""
users/emails.py — All transactional emails sent to users.
"""

from django.core.mail import send_mail
from django.conf import settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from .tokens import email_verification_token, password_reset_token


def send_verification_email(user):
    """Send email with a one-click verification link."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"

    send_mail(
        subject="Verify your Smart Parking email",
        message=(
            f"Hi {user.full_name},\n\n"
            f"Click the link below to verify your email address:\n{link}\n\n"
            "This link expires in 24 hours.\n\n"
            "— Smart Parking Team"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_password_reset_email(user):
    """Send email with a password reset link."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = password_reset_token.make_token(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

    send_mail(
        subject="Reset your Smart Parking password",
        message=(
            f"Hi {user.full_name},\n\n"
            f"Click the link below to reset your password:\n{link}\n\n"
            "If you did not request this, ignore this email.\n\n"
            "— Smart Parking Team"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_booking_confirmation_email(user, booking):
    """Send booking confirmation details."""
    send_mail(
        subject=f"Booking Confirmed — Slot {booking.slot.slot_number}",
        message=(
            f"Hi {user.full_name},\n\n"
            f"Your booking is confirmed!\n\n"
            f"Slot: {booking.slot.slot_number}\n"
            f"From: {booking.start_time.strftime('%d %b %Y, %I:%M %p')}\n"
            f"To:   {booking.end_time.strftime('%d %b %Y, %I:%M %p')}\n"
            f"Estimated cost: ₹{booking.estimated_price}\n\n"
            "— Smart Parking Team"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
