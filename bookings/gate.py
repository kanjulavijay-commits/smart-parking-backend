"""
bookings/gate.py — Gate scanner logic.

When a vehicle arrives at the gate, the gate terminal (a tablet or barcode
reader) POSTs the QR token here. This module:
  1. Validates the QR token (exists, not expired, not already used)
  2. Finds the linked booking
  3. Triggers check-in (entry) or check-out (exit) automatically
  4. Updates EntryExitLog with the real gate_id and timestamp
  5. Returns a clear OPEN / DENY instruction to the gate terminal
"""

from django.utils import timezone
from parking.models import QRCode, EntryExitLog
from .models import Booking
from .services import check_in_booking, check_out_booking


def scan_qr(token, gate_id, scan_type="entry"):
    """
    Process a QR scan at the gate.

    Returns a dict:
      { "action": "OPEN" | "DENY", "message": str, "booking_id": str | None }
    """
    # 1. Find the QR record
    try:
        qr = QRCode.objects.select_related().get(token=token)
    except QRCode.DoesNotExist:
        return _deny("Invalid QR code.")

    # 2. Check expiry
    if qr.expires_at < timezone.now():
        return _deny("QR code has expired.")

    # 3. Find the booking linked to this QR via EntryExitLog
    log = EntryExitLog.objects.filter(qr_code=qr).select_related(
        "vehicle", "slot"
    ).first()

    if not log:
        return _deny("No booking linked to this QR code.")

    # 4. Find the active booking for this vehicle + slot
    booking = Booking.objects.filter(
        vehicle=log.vehicle,
        slot=log.slot,
        status__in=["confirmed", "active"],
    ).order_by("-created_at").first()

    if not booking:
        return _deny("No active booking found for this vehicle.")

    # 5. Entry scan → check in
    if scan_type == "entry":
        if booking.status == "active":
            return _deny("Vehicle is already checked in.")
        try:
            session = check_in_booking(booking)
        except ValueError as e:
            return _deny(str(e))

        # Update the pre-registered log entry
        log.log_type = "entry"
        log.gate_id = gate_id
        log.scanned_at = timezone.now()
        log.notes = "Gate scan — entry confirmed"
        log.save()

        return _open(
            f"Welcome! Proceed to slot {booking.slot.slot_number}.",
            booking_id=str(booking.id),
            session_id=str(session.id),
            slot=booking.slot.slot_number,
        )

    # 6. Exit scan → check out
    if scan_type == "exit":
        if booking.status != "active":
            return _deny("Booking is not active. Cannot check out.")

        try:
            result = check_out_booking(booking)
        except ValueError as e:
            return _deny(str(e))

        # Create an exit log entry
        EntryExitLog.objects.create(
            vehicle=log.vehicle,
            slot=log.slot,
            qr_code=qr,
            log_type="exit",
            gate_id=gate_id,
            notes=f"Gate scan — exit. Duration: {result['session'].duration_minutes} min.",
        )

        # Mark QR as used so it can't be re-scanned
        qr.is_used = True
        qr.used_at = timezone.now()
        qr.save(update_fields=["is_used", "used_at"])

        return _open(
            f"Goodbye! Duration: {result['session'].duration_minutes} min. "
            f"Total: ₹{result['final_price']}. Drive safe!",
            booking_id=str(booking.id),
            duration_minutes=result["session"].duration_minutes,
            final_price=str(result["final_price"]),
        )

    return _deny(f"Unknown scan_type: {scan_type}. Use 'entry' or 'exit'.")


def _open(message, **extra):
    return {"action": "OPEN", "message": message, **extra}


def _deny(message):
    return {"action": "DENY", "message": message, "booking_id": None}


def detect_overstays():
    """
    Finds all active bookings where end_time has passed.
    Sends an overstay notification and records the overstay minutes.
    Called by a management command (or a cron job in production).
    """
    from notifications.models import Notification

    now = timezone.now()
    overstayed = Booking.objects.filter(
        status="active",
        end_time__lt=now,
    ).select_related("user", "slot", "vehicle")

    count = 0
    for booking in overstayed:
        try:
            session = booking.session
        except Exception:
            continue

        overstay_minutes = int((now - booking.end_time).total_seconds() / 60)
        if session.overstay_minutes == overstay_minutes:
            continue  # already notified this minute

        session.overstay_minutes = overstay_minutes
        session.save(update_fields=["overstay_minutes"])

        Notification.objects.get_or_create(
            user=booking.user,
            title="Overstay Alert",
            defaults={
                "message": (
                    f"Your booking for slot {booking.slot.slot_number} ended "
                    f"{overstay_minutes} minutes ago. Additional charges may apply."
                ),
                "category": "alert",
                "channel": "in_app",
                "data": {
                    "booking_id": str(booking.id),
                    "overstay_minutes": overstay_minutes,
                },
            },
        )
        count += 1

    return count
