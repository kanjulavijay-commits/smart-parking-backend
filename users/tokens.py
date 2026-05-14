"""
users/tokens.py — Email verification and password reset token generators.

Django's PasswordResetTokenGenerator uses a hash of user state (password,
last_login, pk) to create one-time-use tokens that expire automatically.
We reuse that same mechanism for email verification.
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Generates a one-time token for verifying a user's email address."""

    def _make_hash_value(self, user, timestamp):
        # Token becomes invalid once is_email_verified flips to True
        return f"{user.pk}{timestamp}{user.is_email_verified}"


class PasswordResetToken(PasswordResetTokenGenerator):
    """Generates a one-time token for resetting a user's password."""

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.password}"


email_verification_token = EmailVerificationTokenGenerator()
password_reset_token = PasswordResetToken()
