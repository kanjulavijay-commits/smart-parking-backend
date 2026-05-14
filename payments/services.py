"""
payments/services.py — All payment business logic.

Handles:
- Payment creation linked to a booking
- Invoice auto-generation with sequential numbering
- Refund policy: full refund >2hr before start, 50% <2hr, no refund after check-in
- Payment summary stats for admin dashboard
"""

from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_transaction
from notifications.models import Notification
from .models import Payment, Transaction, Invoice


def _next_invoice_number():
    """Generate sequential invoice numbers: INV-2026-00001."""
    year = timezone.now().year
    last = Invoice.objects.filter(
        invoice_number__startswith=f"INV-{year}-"
    ).order_by("-invoice_number").first()

    if last:
        seq = int(last.invoice_number.split("-")[-1]) + 1
    else:
        seq = 1

    return f"INV-{year}-{seq:05d}"


def create_payment(booking, method="upi"):
    """
    Create a pending Payment for a booking.
    Called right after booking is confirmed so the user can pay.
    """
    # Avoid duplicate payments
    existing = Payment.objects.filter(booking=booking, status__in=["pending", "success"]).first()
    if existing:
        return existing

    payment = Payment.objects.create(
        booking=booking,
        user=booking.user,
        amount=booking.estimated_price,
        method=method,
        status="pending",
    )

    Notification.objects.create(
        user=booking.user,
        title="Payment Pending",
        message=f"Complete your payment of ₹{payment.amount} for slot {booking.slot.slot_number}.",
        category="payment",
        channel="in_app",
        data={"payment_id": str(payment.id), "amount": str(payment.amount)},
    )

    return payment


@db_transaction.atomic
def confirm_payment(payment):
    """
    Mark a payment as successful, record the debit transaction, generate invoice.
    Uses atomic transaction — if invoice creation fails, payment is rolled back.
    """
    if payment.status != "pending":
        raise ValueError(f"Cannot confirm a {payment.status} payment.")

    payment.status = "success"
    payment.paid_at = timezone.now()
    payment.save(update_fields=["status", "paid_at"])

    # Ledger entry
    Transaction.objects.create(
        payment=payment,
        amount=payment.amount,
        transaction_type="debit",
        description=f"Payment for booking {str(payment.booking.id)[:8]}",
    )

    # Generate invoice
    invoice = _generate_invoice(payment)

    Notification.objects.create(
        user=payment.user,
        title="Payment Successful",
        message=f"₹{payment.amount} paid. Invoice #{invoice.invoice_number} generated.",
        category="payment",
        channel="in_app",
        data={
            "payment_id": str(payment.id),
            "invoice_number": invoice.invoice_number,
            "amount": str(payment.amount),
        },
    )

    return payment, invoice


def _generate_invoice(payment):
    """Create an Invoice record with GST breakdown."""
    # GST = 18% of subtotal; total = subtotal + tax
    total = payment.amount
    # Reverse-calculate subtotal from total (total = subtotal * 1.18)
    subtotal = (total / Decimal("1.18")).quantize(Decimal("0.01"))
    tax = (total - subtotal).quantize(Decimal("0.01"))

    invoice = Invoice.objects.create(
        payment=payment,
        invoice_number=_next_invoice_number(),
        subtotal=subtotal,
        tax=tax,
        total=total,
    )
    return invoice


@db_transaction.atomic
def process_refund(payment, requested_amount=None):
    """
    Refund policy:
    - Cancelled >2 hours before booking start  → 100% refund
    - Cancelled within 2 hours of booking start → 50% refund
    - After check-in (booking is active)        → no refund
    """
    if payment.status != "success":
        raise ValueError("Only successful payments can be refunded.")

    booking = payment.booking
    now = timezone.now()

    if booking.status == "active":
        raise ValueError("Cannot refund a booking that has already been checked in.")

    if requested_amount:
        refund_amount = min(Decimal(str(requested_amount)), payment.amount)
    else:
        hours_until_start = (booking.start_time - now).total_seconds() / 3600
        if hours_until_start >= 2:
            refund_amount = payment.amount  # 100%
        elif hours_until_start > 0:
            refund_amount = (payment.amount * Decimal("0.5")).quantize(Decimal("0.01"))  # 50%
        else:
            refund_amount = Decimal("0.00")  # past start time, no refund

    if refund_amount == Decimal("0.00"):
        raise ValueError("No refund applicable — booking start time has already passed.")

    payment.status = "refunded"
    payment.refunded_at = now
    payment.refund_amount = refund_amount
    payment.save(update_fields=["status", "refunded_at", "refund_amount"])

    # Ledger credit entry
    Transaction.objects.create(
        payment=payment,
        amount=refund_amount,
        transaction_type="credit",
        description=f"Refund for booking {str(booking.id)[:8]}",
    )

    Notification.objects.create(
        user=payment.user,
        title="Refund Processed",
        message=f"₹{refund_amount} refunded to your account. May take 3-5 business days.",
        category="payment",
        channel="in_app",
        data={"payment_id": str(payment.id), "refund_amount": str(refund_amount)},
    )

    return payment


def get_payment_summary(user=None):
    """
    Revenue summary stats for admin dashboard.
    If user is provided, returns that user's personal stats.
    """
    qs = Payment.objects.filter(status="success")
    if user:
        qs = qs.filter(user=user)

    from django.db.models import Sum, Count, Avg
    stats = qs.aggregate(
        total_revenue=Sum("amount"),
        total_transactions=Count("id"),
        avg_transaction=Avg("amount"),
    )

    refunds_qs = Payment.objects.filter(status="refunded")
    if user:
        refunds_qs = refunds_qs.filter(user=user)
    refund_stats = refunds_qs.aggregate(total_refunds=Sum("refund_amount"))

    return {
        "total_revenue": float(stats["total_revenue"] or 0),
        "total_transactions": stats["total_transactions"] or 0,
        "avg_transaction": round(float(stats["avg_transaction"] or 0), 2),
        "total_refunded": float(refund_stats["total_refunds"] or 0),
    }
