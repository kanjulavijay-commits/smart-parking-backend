from rest_framework import serializers
from .models import (
    ParkingLot, ParkingFloor, ParkingZone, ParkingSlot,
    Vehicle, PricingRule, SensorData, ParkingCamera, QRCode, EntryExitLog,
)


class ParkingSlotSerializer(serializers.ModelSerializer):
    slot_type = serializers.SerializerMethodField()

    class Meta:
        model = ParkingSlot
        fields = [
            "id", "zone", "slot_number", "size", "slot_type", "status",
            "has_ev_charger", "is_active", "floor_position_x", "floor_position_y",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_slot_type(self, obj):
        return obj.zone.zone_type


class ParkingZoneSerializer(serializers.ModelSerializer):
    slots = ParkingSlotSerializer(many=True, read_only=True)
    available_slots = serializers.SerializerMethodField()

    class Meta:
        model = ParkingZone
        fields = ["id", "floor", "name", "zone_type", "total_slots", "is_active", "slots", "available_slots"]

    def get_available_slots(self, obj):
        return obj.slots.filter(status="available", is_active=True).count()


class ParkingFloorSerializer(serializers.ModelSerializer):
    zones = ParkingZoneSerializer(many=True, read_only=True)

    class Meta:
        model = ParkingFloor
        fields = ["id", "lot", "name", "floor_number", "total_slots", "is_active", "zones"]


class ParkingLotSerializer(serializers.ModelSerializer):
    floors = ParkingFloorSerializer(many=True, read_only=True)
    available_count = serializers.SerializerMethodField()

    class Meta:
        model = ParkingLot
        fields = [
            "id", "name", "address", "city", "state", "country",
            "latitude", "longitude", "total_capacity", "is_active",
            "operating_hours_start", "operating_hours_end",
            "floors", "available_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_available_count(self, obj):
        return ParkingSlot.objects.filter(
            zone__floor__lot=obj, status="available", is_active=True
        ).count()


class ParkingLotListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing lots without nested data."""
    available_slots = serializers.SerializerMethodField()
    base_hourly_rate = serializers.SerializerMethodField()

    class Meta:
        model = ParkingLot
        fields = [
            "id", "name", "address", "city", "total_capacity",
            "is_active", "available_slots", "base_hourly_rate",
        ]

    def get_available_slots(self, obj):
        return ParkingSlot.objects.filter(
            zone__floor__lot=obj, status="available", is_active=True
        ).count()

    def get_base_hourly_rate(self, obj):
        rule = obj.pricing_rules.filter(pricing_type="hourly", is_active=True).order_by("base_price").first()
        return str(rule.base_price) if rule else "0.00"


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            "id", "owner", "license_plate", "vehicle_type",
            "make", "model", "color", "year", "is_default", "created_at",
        ]
        read_only_fields = ["id", "owner", "created_at"]


class PricingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingRule
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


class SensorDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorData
        fields = ["id", "slot", "is_occupied", "confidence_score", "raw_value", "recorded_at"]
        read_only_fields = ["id", "recorded_at"]


class ParkingCameraSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParkingCamera
        fields = "__all__"
        read_only_fields = ["id"]


class QRCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = QRCode
        fields = ["id", "token", "qr_image", "is_used", "used_at", "expires_at", "created_at"]
        read_only_fields = ["id", "token", "is_used", "used_at", "created_at"]


class EntryExitLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntryExitLog
        fields = "__all__"
        read_only_fields = ["id", "scanned_at"]
