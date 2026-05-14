from django.contrib import admin
from .models import (
    ParkingLot, ParkingFloor, ParkingZone, ParkingSlot,
    Vehicle, PricingRule, SensorData, ParkingCamera, QRCode, EntryExitLog,
)


@admin.register(ParkingLot)
class ParkingLotAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "total_capacity", "is_active"]
    list_filter = ["is_active", "city"]
    search_fields = ["name", "city", "address"]


@admin.register(ParkingFloor)
class ParkingFloorAdmin(admin.ModelAdmin):
    list_display = ["name", "lot", "floor_number", "total_slots", "is_active"]
    list_filter = ["is_active", "lot"]


@admin.register(ParkingZone)
class ParkingZoneAdmin(admin.ModelAdmin):
    list_display = ["name", "floor", "zone_type", "total_slots", "is_active"]
    list_filter = ["zone_type", "is_active"]


@admin.register(ParkingSlot)
class ParkingSlotAdmin(admin.ModelAdmin):
    list_display = ["slot_number", "zone", "size", "status", "has_ev_charger", "is_active"]
    list_filter = ["status", "size", "has_ev_charger", "is_active"]
    search_fields = ["slot_number"]


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ["license_plate", "owner", "vehicle_type", "make", "model", "color"]
    list_filter = ["vehicle_type"]
    search_fields = ["license_plate", "owner__email"]


@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "lot", "pricing_type", "base_price", "is_active"]
    list_filter = ["pricing_type", "is_active"]


@admin.register(SensorData)
class SensorDataAdmin(admin.ModelAdmin):
    list_display = ["slot", "is_occupied", "confidence_score", "recorded_at"]
    list_filter = ["is_occupied"]


@admin.register(ParkingCamera)
class ParkingCameraAdmin(admin.ModelAdmin):
    list_display = ["name", "zone", "ip_address", "is_active", "last_seen"]
    list_filter = ["is_active"]


@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ["token", "is_used", "expires_at", "created_at"]
    list_filter = ["is_used"]


@admin.register(EntryExitLog)
class EntryExitLogAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "log_type", "slot", "gate_id", "scanned_at"]
    list_filter = ["log_type"]
    search_fields = ["vehicle__license_plate"]
