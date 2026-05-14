"""
notifications/models.py — Model 14: Notification
"""

import uuid
from django.db import models
from django.conf import settings


class Notification(models.Model):
    """Model 14 — System notification sent to a user (email, push, in-app)."""

    BOOKING = "booking"
    PAYMENT = "payment"
    ALERT = "alert"
    PROMO = "promo"
    SYSTEM = "system"
    CATEGORY_CHOICES = [
        (BOOKING, "Booking"),
        (PAYMENT, "Payment"),
        (ALERT, "Alert"),
        (PROMO, "Promotion"),
        (SYSTEM, "System"),
    ]

    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"
    SMS = "sms"
    CHANNEL_CHOICES = [
        (EMAIL, "Email"),
        (PUSH, "Push Notification"),
        (IN_APP, "In-App"),
        (SMS, "SMS"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default=SYSTEM)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default=IN_APP)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.category}] {self.title} → {self.user}"

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
