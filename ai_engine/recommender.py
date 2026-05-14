"""
ai_engine/recommender.py — AI-powered slot recommendation engine.

Recommends the best available parking slot for a user based on:
  1. Distance from entrance (prefer closer slots)
  2. Historical preference (user previously chose EV / covered / specific zone)
  3. Vehicle type compatibility (size match)
  4. Current availability and pricing
  5. Predicted availability at requested time (from sensor data trends)

This is a rule-based + scoring approach — no ML model needed here.
A future version can swap in a collaborative filtering model.
"""

from decimal import Decimal
from django.db.models import Avg, Count
from parking.models import ParkingSlot, ParkingLot
from parking.services import calculate_price
from .models import AIRecommendation


VEHICLE_SIZE_MAP = {
    "bike": "small",
    "car": "medium",
    "ev": "medium",
    "truck": "large",
}

ZONE_PREFERENCE_MAP = {
    "ev": 2.0,        # EV vehicles get EV zone bonus
    "handicap": 1.5,  # bonus for users who historically book handicap
}


def recommend_slot(user, vehicle, lot, start_time, end_time, top_n=3):
    """
    Find the top-N recommended slots for a booking request.

    Scoring formula (higher = better):
      score = (1 / (distance + 1)) * 0.4
            + zone_preference_bonus * 0.2
            + (1 / (price + 1)) * 0.3
            + availability_confidence * 0.1

    Returns a list of AIRecommendation instances (saved to DB).
    """
    from bookings.models import Booking

    size = VEHICLE_SIZE_MAP.get(vehicle.vehicle_type, "medium")

    # Get available slots of the right size
    booked_ids = Booking.objects.filter(
        slot__zone__floor__lot=lot,
        status__in=["confirmed", "active"],
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).values_list("slot_id", flat=True)

    candidates = ParkingSlot.objects.filter(
        zone__floor__lot=lot,
        status="available",
        size=size,
        is_active=True,
    ).exclude(id__in=booked_ids).select_related(
        "zone__floor"
    )[:50]

    if not candidates:
        return []

    # Get user's historical zone preferences
    user_preferred_zone = _get_user_zone_preference(user)

    scored = []
    for slot in candidates:
        score = _score_slot(slot, vehicle, user_preferred_zone, start_time, end_time)
        price_info = calculate_price(slot, vehicle.vehicle_type, start_time, end_time)
        scored.append((score, slot, price_info))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_n]

    recommendations = []
    for rank, (score, slot, price_info) in enumerate(top):
        rec = AIRecommendation.objects.create(
            user=user,
            recommendation_type="slot",
            recommended_slot=slot,
            recommended_lot=lot,
            confidence=round(min(score, 1.0), 3),
            reasoning=_build_reasoning(rank, slot, price_info, score),
            context_data={
                "vehicle_type": vehicle.vehicle_type,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "estimated_price": price_info["total"],
                "rank": rank + 1,
            },
        )
        recommendations.append(rec)

    return recommendations


def _score_slot(slot, vehicle, user_preferred_zone, start_time, end_time):
    """Calculate a 0–1 composite score for a slot."""

    # Distance score: lower floor number + lower slot position = closer to entrance
    floor_bonus = 1 / (slot.zone.floor.floor_number + 1)
    position_bonus = 1 / (
        (slot.floor_position_x or 0) + (slot.floor_position_y or 0) + 1
    )
    distance_score = (floor_bonus + position_bonus) / 2

    # Zone preference score
    zone_score = 0.5
    if vehicle.vehicle_type == "ev" and slot.zone.zone_type == "ev":
        zone_score = 1.0
    elif slot.zone.zone_type == user_preferred_zone:
        zone_score = 0.8
    elif slot.zone.zone_type == "standard":
        zone_score = 0.6

    # EV charger bonus for EV vehicles
    ev_bonus = 0.2 if (vehicle.vehicle_type == "ev" and slot.has_ev_charger) else 0.0

    # Price score: cheaper = higher score
    try:
        price_info = calculate_price(slot, vehicle.vehicle_type, start_time, end_time)
        total = price_info["total"]
        price_score = 1 / (total / 100 + 1)  # normalize around ₹100/hr baseline
    except Exception:
        price_score = 0.5

    # Composite weighted score
    score = (
        distance_score * 0.35
        + zone_score * 0.30
        + price_score * 0.25
        + ev_bonus * 0.10
    )
    return round(score, 4)


def _get_user_zone_preference(user):
    """Find the zone type the user books most often."""
    from bookings.models import Booking
    result = (
        Booking.objects.filter(user=user, status="completed")
        .values("slot__zone__zone_type")
        .annotate(count=Count("id"))
        .order_by("-count")
        .first()
    )
    return result["slot__zone__zone_type"] if result else "standard"


def _build_reasoning(rank, slot, price_info, score):
    reasons = []
    if rank == 0:
        reasons.append("Best overall match for your vehicle and preferences.")
    if slot.zone.floor.floor_number == 0:
        reasons.append("Ground floor — easy access from entrance.")
    if slot.has_ev_charger:
        reasons.append("EV charging available at this slot.")
    if slot.zone.zone_type == "covered":
        reasons.append("Covered parking — weather protected.")
    reasons.append(f"Estimated cost: ₹{price_info['total']} (incl. GST).")
    return " ".join(reasons)


def recommend_time(user, lot, vehicle):
    """
    Suggest the cheapest/least-busy time window for parking today.
    Based on sensor data occupancy trends.
    """
    from parking.models import SensorData
    from django.utils import timezone
    import datetime

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    hourly_occ = {}
    for hour in range(6, 23):
        hour_start = today_start + datetime.timedelta(hours=hour)
        hour_end = hour_start + datetime.timedelta(hours=1)
        avg = SensorData.objects.filter(
            slot__zone__floor__lot=lot,
            recorded_at__range=(hour_start, hour_end),
        ).aggregate(avg=Avg("confidence_score"))["avg"] or 0
        hourly_occ[hour] = round(avg, 2)

    if not hourly_occ:
        best_hour = 10  # fallback
    else:
        best_hour = min(hourly_occ, key=hourly_occ.get)

    rec = AIRecommendation.objects.create(
        user=user,
        recommendation_type="time",
        recommended_lot=lot,
        confidence=0.70,
        reasoning=(
            f"Based on historical sensor data, {best_hour}:00 has the lowest occupancy "
            f"at this lot. Arriving then increases your chance of finding a spot quickly."
        ),
        context_data={"hourly_occupancy": hourly_occ, "recommended_hour": best_hour},
    )
    return rec
