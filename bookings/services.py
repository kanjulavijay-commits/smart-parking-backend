"""
bookings/services.py — All booking business logic lives here.

Views stay thin. This module handles:
- Price auto-calculation at booking creation
- QR code generation (one per booking)
- In-app + email notifications
- Status transition enforcement
"""

import uuid
import qrcode
import io
from decimal import Decimal
from django.utils import timezone
from django.core.files.base import ContentFile
from django.conf import settings
from parking.models import ParkingSlot, QRCode
from parking.services import calculate_price
from notifications.models import Notification


def create_booking(user, vehicle, slot, booking_type, start_time, end_time):
    """
    Full booking creation flow:
    1. Calculate price
    2. Create Booking record
    3. Reserve the slot
    4. Generate QR code
    5. Fire notifications

    Returns the created Booking instance.
    """
    from .models import Booking

    # 1. Calculate price using the pricing engine
    price_breakdown = calculate_price(slot, vehicle.vehicle_type, start_time, end_time)
    estimated_price = Decimal(str(price_breakdown["total"]))

    # 2. Create the booking
    booking = Booking.objects.create(
        user=user,
        vehicle=vehicle,
        slot=slot,
        booking_type=booking_type,
        status="confirmed",
        start_time=start_time,
        end_time=end_time,
        estimated_price=estimated_price,
    )

    # 3. Reserve the slot immediately
    slot.status = "reserved"
    slot.save(update_fields=["status"])

    # 4. Generate QR code for gate scan
    _generate_qr(booking)

    # 5. Auto-create a pending payment for the booking
    from payments.services import create_payment
    create_payment(booking)

    # 6. In-app notification
    _notify_booking_confirmed(user, booking)

    # 7. Send email (non-blocking — fails silently)
    try:
        from users.emails import send_booking_confirmation_email
        send_booking_confirmation_email(user, booking)
    except Exception:
        pass

    return booking


def cancel_booking(booking, reason=""):
    """Cancel a booking and free the slot."""
    if booking.status in ["completed", "cancelled"]:
        raise ValueError(f"Cannot cancel a {booking.status} booking.")

    booking.status = "cancelled"
    booking.cancellation_reason = reason
    booking.cancelled_at = timezone.now()
    booking.save(update_fields=["status", "cancellation_reason", "cancelled_at"])

    booking.slot.status = "available"
    booking.slot.save(update_fields=["status"])

    Notification.objects.create(
        user=booking.user,
        title="Booking Cancelled",
        message=f"Your booking for slot {booking.slot.slot_number} has been cancelled.",
        category="booking",
        channel="in_app",
        data={"booking_id": str(booking.id)},
    )
    return booking


def check_in_booking(booking):
    """Mark arrival — starts the VehicleSession clock."""
    from .models import VehicleSession

    if booking.status != "confirmed":
        raise ValueError("Booking must be confirmed to check in.")

    now = timezone.now()
    booking.status = "active"
    booking.actual_start = now
    booking.save(update_fields=["status", "actual_start"])

    booking.slot.status = "occupied"
    booking.slot.save(update_fields=["status"])

    session, _ = VehicleSession.objects.get_or_create(
        booking=booking,
        defaults={"vehicle": booking.vehicle, "slot": booking.slot, "check_in": now},
    )

    Notification.objects.create(
        user=booking.user,
        title="Checked In",
        message=f"Your vehicle is checked in to slot {booking.slot.slot_number}.",
        category="booking",
        channel="in_app",
        data={"booking_id": str(booking.id), "session_id": str(session.id)},
    )
    return session


def check_out_booking(booking):
    """Mark departure — closes session, calculates final price."""
    if booking.status != "active":
        raise ValueError("Booking is not active.")

    now = timezone.now()
    session = booking.session
    session.check_out = now
    session.is_active = False

    if session.check_in:
        delta = now - session.check_in
        session.duration_minutes = int(delta.total_seconds() / 60)
        # Overstay = time beyond originally booked end_time
        if now > booking.end_time:
            overstay = now - booking.end_time
            session.overstay_minutes = int(overstay.total_seconds() / 60)

    session.save()

    # Recalculate final price based on actual duration
    actual_end = now
    price_breakdown = calculate_price(
        booking.slot, booking.vehicle.vehicle_type,
        booking.actual_start, actual_end,
    )
    final_price = Decimal(str(price_breakdown["total"]))

    booking.status = "completed"
    booking.actual_end = now
    booking.final_price = final_price
    booking.save(update_fields=["status", "actual_end", "final_price"])

    booking.slot.status = "available"
    booking.slot.save(update_fields=["status"])

    Notification.objects.create(
        user=booking.user,
        title="Checked Out",
        message=(
            f"You've checked out from slot {booking.slot.slot_number}. "
            f"Duration: {session.duration_minutes} min. Total: ₹{final_price}"
        ),
        category="booking",
        channel="in_app",
        data={
            "booking_id": str(booking.id),
            "duration_minutes": session.duration_minutes,
            "final_price": str(final_price),
        },
    )
    return {"session": session, "final_price": final_price, "price_breakdown": price_breakdown}


def _generate_qr(booking):
    """Create a QR code image for the booking and attach it via the QRCode model."""
    token = str(uuid.uuid4())
    expires_at = booking.end_time

    qr_record = QRCode.objects.create(
        token=token,
        expires_at=expires_at,
    )

    # Generate the QR image in-memory (no external service needed)
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(f"SMARTPARK:{token}:BOOKING:{booking.id}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    filename = f"qr_{booking.id}.png"
    qr_record.qr_image.save(filename, ContentFile(buffer.read()), save=True)

    # Link QR to booking via the EntryExitLog model (pre-register for gate)
    from parking.models import EntryExitLog
    EntryExitLog.objects.create(
        vehicle=booking.vehicle,
        slot=booking.slot,
        qr_code=qr_record,
        log_type="entry",
        gate_id="PENDING",
        notes="Pre-registered by booking system",
    )

    return qr_record


def _notify_booking_confirmed(user, booking):
    Notification.objects.create(
        user=user,
        title="Booking Confirmed",
        message=(
            f"Slot {booking.slot.slot_number} is reserved for you from "
            f"{booking.start_time.strftime('%d %b, %I:%M %p')} to "
            f"{booking.end_time.strftime('%I:%M %p')}. "
            f"Estimated cost: ₹{booking.estimated_price}"
        ),
        category="booking",
        channel="in_app",
        data={
            "booking_id": str(booking.id),
            "slot": booking.slot.slot_number,
            "estimated_price": str(booking.estimated_price),
        },
    )
