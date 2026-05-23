"""
Management command: python manage.py seed
Seeds the database with realistic parking lot data for development & testing.
"""

from django.core.management.base import BaseCommand
from parking.models import (
    ParkingLot, ParkingFloor, ParkingZone, ParkingSlot, PricingRule
)


class Command(BaseCommand):
    help = "Seed database with sample parking lots, floors, zones, slots, and pricing rules."

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding parking data...")

        # ── Parking Lot ───────────────────────────────────────
        lot, _ = ParkingLot.objects.get_or_create(
            name="Phoenix MarketCity Parking",
            defaults={
                "address": "Whitefield Main Road",
                "city": "Bangalore",
                "state": "Karnataka",
                "country": "India",
                "latitude": 12.9716,
                "longitude": 77.7480,
                "total_capacity": 120,
                "is_active": True,
            },
        )
        self.stdout.write(f"  Lot: {lot.name}")

        # ── Pricing Rules ─────────────────────────────────────
        PricingRule.objects.get_or_create(
            lot=lot, name="Standard Hourly",
            defaults={
                "pricing_type": "hourly",
                "base_price": "50.00",
                "peak_hour_multiplier": "1.5",
                "peak_start_time": "09:00",
                "peak_end_time": "20:00",
                "is_active": True,
            },
        )
        PricingRule.objects.get_or_create(
            lot=lot, name="EV Charging Hourly",
            defaults={
                "pricing_type": "hourly",
                "base_price": "80.00",
                "zone_type": "ev",
                "peak_hour_multiplier": "1.0",
                "is_active": True,
            },
        )
        PricingRule.objects.get_or_create(
            lot=lot, name="Bike Rate",
            defaults={
                "pricing_type": "hourly",
                "base_price": "20.00",
                "vehicle_type": "bike",
                "peak_hour_multiplier": "1.0",
                "is_active": True,
            },
        )
        self.stdout.write("  Pricing rules created.")

        # ── Floors ───────────────────────────────────────────
        for floor_num, floor_name in [(0, "Ground"), (1, "Level 1"), (2, "Level 2")]:
            floor, _ = ParkingFloor.objects.get_or_create(
                lot=lot, floor_number=floor_num,
                defaults={"name": floor_name, "total_slots": 40, "is_active": True},
            )

            # ── Zones per floor ───────────────────────────────
            zone_configs = [
                ("Zone A", "standard", 15),
                ("Zone B", "standard", 15),
                ("EV Zone", "ev", 5),
                ("Handicap", "handicap", 5),
            ]
            slot_counter = floor_num * 40 + 1

            for zone_name, zone_type, zone_capacity in zone_configs:
                zone, _ = ParkingZone.objects.get_or_create(
                    floor=floor, name=zone_name,
                    defaults={
                        "zone_type": zone_type,
                        "total_slots": zone_capacity,
                        "is_active": True,
                    },
                )

                # ── Slots per zone ────────────────────────────
                size = "small" if zone_type == "handicap" else "medium"
                ev = zone_type == "ev"

                for i in range(zone_capacity):
                    slot_number = f"{floor_name[0]}{slot_counter:03d}"
                    ParkingSlot.objects.get_or_create(
                        zone=zone, slot_number=slot_number,
                        defaults={
                            "size": size,
                            "status": "available",
                            "has_ev_charger": ev,
                            "floor_position_x": (i % 5) * 2.5,
                            "floor_position_y": (i // 5) * 5.0,
                            "is_active": True,
                        },
                    )
                    slot_counter += 1

        # ── Lot 2: Indiranagar ───────────────────────────────
        lot2, _ = ParkingLot.objects.get_or_create(
            name="Indiranagar 100ft Road Parking",
            defaults={
                "address": "100 Feet Road, Indiranagar",
                "city": "Bangalore",
                "state": "Karnataka",
                "country": "India",
                "latitude": 12.9784,
                "longitude": 77.6408,
                "total_capacity": 80,
                "is_active": True,
            },
        )
        PricingRule.objects.get_or_create(
            lot=lot2, name="Standard Hourly",
            defaults={
                "pricing_type": "hourly",
                "base_price": "40.00",
                "peak_hour_multiplier": "1.5",
                "peak_start_time": "18:00",
                "peak_end_time": "23:00",
                "is_active": True,
            },
        )
        for floor_num, floor_name in [(0, "Ground"), (1, "Level 1")]:
            floor2, _ = ParkingFloor.objects.get_or_create(
                lot=lot2, floor_number=floor_num,
                defaults={"name": floor_name, "total_slots": 40, "is_active": True},
            )
            zone_configs2 = [
                ("Zone A", "standard", 20),
                ("Zone B", "standard", 15),
                ("EV Zone", "ev", 5),
            ]
            ctr = floor_num * 40 + 1
            for zname, ztype, zcap in zone_configs2:
                zone2, _ = ParkingZone.objects.get_or_create(
                    floor=floor2, name=zname,
                    defaults={"zone_type": ztype, "total_slots": zcap, "is_active": True},
                )
                for i in range(zcap):
                    ParkingSlot.objects.get_or_create(
                        zone=zone2,
                        slot_number=f"I{ctr:03d}",
                        defaults={
                            "size": "medium",
                            "status": "available",
                            "has_ev_charger": ztype == "ev",
                            "floor_position_x": (i % 5) * 2.5,
                            "floor_position_y": (i // 5) * 5.0,
                            "is_active": True,
                        },
                    )
                    ctr += 1

        # ── Lot 3: Electronic City ────────────────────────────
        lot3, _ = ParkingLot.objects.get_or_create(
            name="Electronic City Tech Park Parking",
            defaults={
                "address": "Phase 1, Electronic City",
                "city": "Bangalore",
                "state": "Karnataka",
                "country": "India",
                "latitude": 12.8399,
                "longitude": 77.6770,
                "total_capacity": 60,
                "is_active": True,
            },
        )
        PricingRule.objects.get_or_create(
            lot=lot3, name="Office Hourly",
            defaults={
                "pricing_type": "hourly",
                "base_price": "30.00",
                "peak_hour_multiplier": "1.2",
                "peak_start_time": "08:00",
                "peak_end_time": "18:00",
                "is_active": True,
            },
        )
        floor3, _ = ParkingFloor.objects.get_or_create(
            lot=lot3, floor_number=0,
            defaults={"name": "Ground", "total_slots": 60, "is_active": True},
        )
        for zname, ztype, zcap in [("Zone A", "standard", 30), ("Zone B", "standard", 20), ("EV Zone", "ev", 10)]:
            zone3, _ = ParkingZone.objects.get_or_create(
                floor=floor3, name=zname,
                defaults={"zone_type": ztype, "total_slots": zcap, "is_active": True},
            )
            for i in range(zcap):
                ParkingSlot.objects.get_or_create(
                    zone=zone3,
                    slot_number=f"E{i+1:03d}",
                    defaults={
                        "size": "medium",
                        "status": "available",
                        "has_ev_charger": ztype == "ev",
                        "floor_position_x": (i % 5) * 2.5,
                        "floor_position_y": (i // 5) * 5.0,
                        "is_active": True,
                    },
                )

        total_slots = ParkingSlot.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"\nDone! Seeded: 3 lots, floors, zones, {total_slots} total slots."
        ))
