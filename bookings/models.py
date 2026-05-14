"""
bookings/models.py — Models 8, 10: Booking, VehicleSession
"""

import uuid
from django.db import models
from django.conf import settings


class Booking(models.Model):
    """Model 8 — A reservation made by a driver for a specific slot."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (CONFIRMED, "Confirmed"),
        (ACTIVE, "Active"),
        (COMPLETED, "Completed"),
        (CANCELLED, "Cancelled"),
        (NO_SHOW, "No Show"),
    ]

    INSTANT = "instant"
    SCHEDULED = "scheduled"
    BOOKING_TYPES = [
        (INSTANT, "Instant"),
        (SCHEDULED, "Scheduled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings"
    )
    vehicle = models.ForeignKey(
        "parking.Vehicle", on_delete=models.CASCADE, related_name="bookings"
    )
    slot = models.ForeignKey(
        "parking.ParkingSlot", on_delete=models.CASCADE, related_name="bookings"
    )
    booking_type = models.CharField(max_length=10, choices=BOOKING_TYPES, default=INSTANT)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=PENDING)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    estimated_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Booking #{str(self.id)[:8]} — {self.user} [{self.status}]"

    class Meta:
        db_table = "bookings"
        ordering = ["-created_at"]


class VehicleSession(models.Model):
    """Model 10 — Tracks the actual physical session of a vehicle in a slot (entry to exit)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="session")
    vehicle = models.ForeignKey(
        "parking.Vehicle", on_delete=models.CASCADE, related_name="sessions"
    )
    slot = models.ForeignKey(
        "parking.ParkingSlot", on_delete=models.CASCADE, related_name="sessions"
    )
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    overstay_minutes = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session: {self.vehicle.license_plate} @ Slot {self.slot.slot_number}"

    class Meta:
        db_table = "vehicle_sessions"
        ordering = ["-created_at"]
