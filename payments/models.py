"""
payments/models.py — Models 11, 12, 13, 22, 23, 24
Payment, Transaction, Invoice, Subscription, Review, Rating
"""

import uuid
from django.db import models
from django.conf import settings


class Payment(models.Model):
    """Model 11 — A payment record tied to a booking."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (SUCCESS, "Success"),
        (FAILED, "Failed"),
        (REFUNDED, "Refunded"),
    ]

    CASH = "cash"
    CARD = "card"
    UPI = "upi"
    WALLET = "wallet"
    METHOD_CHOICES = [
        (CASH, "Cash"),
        (CARD, "Card"),
        (UPI, "UPI"),
        (WALLET, "Wallet"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(
        "bookings.Booking", on_delete=models.CASCADE, related_name="payment"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default=UPI)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    gateway_reference = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment ₹{self.amount} — {self.status}"

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]


class Transaction(models.Model):
    """Model 12 — Every financial movement (debit/credit) linked to a payment."""

    DEBIT = "debit"
    CREDIT = "credit"
    TYPES = [(DEBIT, "Debit"), (CREDIT, "Credit")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TYPES)
    reference_id = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type.upper()} ₹{self.amount}"

    class Meta:
        db_table = "transactions"
        ordering = ["-created_at"]


class Invoice(models.Model):
    """Model 13 — PDF-ready invoice generated after a successful payment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name="invoice")
    invoice_number = models.CharField(max_length=50, unique=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    pdf_file = models.FileField(upload_to="invoices/", blank=True, null=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice #{self.invoice_number} — ₹{self.total}"

    class Meta:
        db_table = "invoices"
        ordering = ["-issued_at"]


class Subscription(models.Model):
    """Model 22 — Monthly/yearly parking plan purchased by a driver."""

    MONTHLY = "monthly"
    YEARLY = "yearly"
    PLAN_TYPES = [
        (MONTHLY, "Monthly"),
        (YEARLY, "Yearly"),
    ]

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (ACTIVE, "Active"),
        (EXPIRED, "Expired"),
        (CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions"
    )
    lot = models.ForeignKey("parking.ParkingLot", on_delete=models.CASCADE, related_name="subscriptions")
    plan_type = models.CharField(max_length=10, choices=PLAN_TYPES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ACTIVE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.plan_type} plan [{self.status}]"

    class Meta:
        db_table = "subscriptions"
        ordering = ["-created_at"]


class Review(models.Model):
    """Model 23 — Written review left by a driver about a parking lot."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    lot = models.ForeignKey("parking.ParkingLot", on_delete=models.CASCADE, related_name="reviews")
    title = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review by {self.user} on {self.lot}"

    class Meta:
        db_table = "reviews"
        ordering = ["-created_at"]
        unique_together = ["user", "lot"]


class Rating(models.Model):
    """Model 24 — Star rating (1-5) for a parking lot by a driver."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings"
    )
    lot = models.ForeignKey("parking.ParkingLot", on_delete=models.CASCADE, related_name="ratings")
    score = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if not (1 <= self.score <= 5):
            raise ValidationError("Rating score must be between 1 and 5.")

    def __str__(self):
        return f"{self.user} rated {self.lot} — {self.score}/5"

    class Meta:
        db_table = "ratings"
        unique_together = ["user", "lot"]
