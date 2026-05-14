"""
parking/services.py — Business logic for pricing and availability.

Keeping logic out of views keeps views thin and makes it easy to test
or reuse the same calculations in multiple places (API, admin, AI engine).
"""

from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from .models import ParkingLot, ParkingSlot, PricingRule


def calculate_price(slot, vehicle_type, start_time, end_time):
    """
    Calculate the estimated price for a booking.

    Steps:
    1. Find the best matching PricingRule for this slot's lot and vehicle type.
    2. Determine if the booking falls in peak hours.
    3. Calculate duration and multiply by rate.

    Returns a dict with breakdown details.
    """
    lot = slot.zone.floor.lot
    zone_type = slot.zone.zone_type
    duration_seconds = (end_time - start_time).total_seconds()
    duration_hours = Decimal(str(duration_seconds / 3600))

    # Find the most specific pricing rule (vehicle + zone match beats generic)
    rule = (
        PricingRule.objects.filter(
            lot=lot, is_active=True,
            vehicle_type=vehicle_type, zone_type=zone_type,
        ).first()
        or PricingRule.objects.filter(
            lot=lot, is_active=True, vehicle_type=vehicle_type, zone_type__isnull=True
        ).first()
        or PricingRule.objects.filter(
            lot=lot, is_active=True, vehicle_type__isnull=True, zone_type=zone_type
        ).first()
        or PricingRule.objects.filter(
            lot=lot, is_active=True, vehicle_type__isnull=True, zone_type__isnull=True
        ).first()
    )

    if not rule:
        # Default fallback rate: ₹50/hour
        base_rate = Decimal("50.00")
        multiplier = Decimal("1.0")
        rule_name = "Default Rate"
    else:
        base_rate = rule.base_price
        multiplier = _get_peak_multiplier(rule, start_time)
        rule_name = rule.name

    if rule and rule.pricing_type == "daily":
        duration_units = Decimal(str(duration_seconds / 86400))
    else:
        duration_units = duration_hours

    subtotal = (base_rate * duration_units * multiplier).quantize(Decimal("0.01"))
    tax = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))  # 18% GST
    total = subtotal + tax

    return {
        "rule_name": rule_name,
        "base_rate": float(base_rate),
        "duration_hours": float(duration_hours),
        "peak_multiplier": float(multiplier),
        "subtotal": float(subtotal),
        "tax_gst_18": float(tax),
        "total": float(total),
    }


def _get_peak_multiplier(rule, start_time):
    """Return 1.0 if not peak hour, or rule.peak_hour_multiplier if it is."""
    if not rule.peak_start_time or not rule.peak_end_time:
        return Decimal("1.0")
    booking_time = start_time.time()
    if rule.peak_start_time <= booking_time <= rule.peak_end_time:
        return rule.peak_hour_multiplier
    return Decimal("1.0")


def get_lot_availability_summary(lot):
    """Return full slot counts broken down by floor → zone."""
    summary = {"lot_id": str(lot.id), "lot_name": lot.name, "floors": []}
    total_all = 0
    available_all = 0

    for floor in lot.floors.filter(is_active=True).order_by("floor_number"):
        floor_data = {"floor": floor.name, "floor_number": floor.floor_number, "zones": []}
        for zone in floor.zones.filter(is_active=True).order_by("name"):
            slots = zone.slots.filter(is_active=True)
            total = slots.count()
            available = slots.filter(status="available").count()
            occupied = slots.filter(status="occupied").count()
            reserved = slots.filter(status="reserved").count()
            total_all += total
            available_all += available
            floor_data["zones"].append({
                "zone_id": str(zone.id),
                "zone_name": zone.name,
                "zone_type": zone.zone_type,
                "total": total,
                "available": available,
                "occupied": occupied,
                "reserved": reserved,
                "occupancy_pct": round((occupied / total * 100) if total else 0, 1),
            })
        summary["floors"].append(floor_data)

    summary["total_slots"] = total_all
    summary["available_slots"] = available_all
    summary["occupancy_pct"] = round(
        ((total_all - available_all) / total_all * 100) if total_all else 0, 1
    )
    return summary


def find_nearest_lots(latitude, longitude, radius_km=10):
    """
    Return active parking lots sorted by distance from the given coordinates.
    Uses the Haversine approximation (flat-earth is good enough under ~50 km).
    """
    import math

    lots = ParkingLot.objects.filter(
        is_active=True,
        latitude__isnull=False,
        longitude__isnull=False,
    )

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371  # Earth radius in km
        d_lat = math.radians(float(lat2) - float(lat1))
        d_lon = math.radians(float(lon2) - float(lon1))
        a = (math.sin(d_lat / 2) ** 2
             + math.cos(math.radians(float(lat1)))
             * math.cos(math.radians(float(lat2)))
             * math.sin(d_lon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    results = []
    for lot in lots:
        dist = haversine(latitude, longitude, lot.latitude, lot.longitude)
        if dist <= radius_km:
            available = ParkingSlot.objects.filter(
                zone__floor__lot=lot, status="available", is_active=True
            ).count()
            results.append({
                "lot_id": str(lot.id),
                "name": lot.name,
                "address": lot.address,
                "city": lot.city,
                "latitude": float(lot.latitude),
                "longitude": float(lot.longitude),
                "distance_km": round(dist, 2),
                "available_slots": available,
                "total_capacity": lot.total_capacity,
            })

    results.sort(key=lambda x: x["distance_km"])
    return results
