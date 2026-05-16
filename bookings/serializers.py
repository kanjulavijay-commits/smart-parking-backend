from rest_framework import serializers
from django.utils import timezone
from .models import Booking, VehicleSession
from parking.models import Vehicle


class BookingSerializer(serializers.ModelSerializer):
    # Accept a plain license plate string — we find/create the Vehicle automatically
    vehicle_plate = serializers.CharField(write_only=True, required=False)
    vehicle = serializers.PrimaryKeyRelatedField(
        queryset=Vehicle.objects.all(), required=False
    )
    # Read-only summary displayed on booking cards and detail page
    slot_info = serializers.SerializerMethodField()
    # Alias so frontend can use booking.total_amount consistently
    total_amount = serializers.DecimalField(source="estimated_price", max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "user", "vehicle", "vehicle_plate", "slot", "slot_info",
            "booking_type", "status", "start_time", "end_time",
            "actual_start", "actual_end", "estimated_price", "total_amount",
            "final_price", "cancellation_reason", "cancelled_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "user", "status", "actual_start", "actual_end",
            "final_price", "cancelled_at", "created_at", "updated_at",
        ]

    def get_slot_info(self, obj):
        slot = obj.slot
        return {
            "slot_number": slot.slot_number,
            "lot_name": slot.zone.floor.lot.name,
            "floor": slot.zone.floor.name,
            "zone": slot.zone.name,
        }

    def validate(self, attrs):
        # Resolve vehicle: either a Vehicle FK or a plate string
        vehicle_plate = attrs.pop("vehicle_plate", None)
        if not attrs.get("vehicle"):
            if not vehicle_plate:
                raise serializers.ValidationError(
                    {"vehicle_plate": "Provide a vehicle plate number."}
                )
            user = self.context["request"].user
            vehicle, _ = Vehicle.objects.get_or_create(
                license_plate=vehicle_plate.strip().upper(),
                defaults={"owner": user, "vehicle_type": "car"},
            )
            attrs["vehicle"] = vehicle

        if attrs["start_time"] >= attrs["end_time"]:
            raise serializers.ValidationError("end_time must be after start_time.")
        if attrs["start_time"] < timezone.now():
            raise serializers.ValidationError("Cannot book a slot in the past.")

        slot = attrs["slot"]
        if slot.status not in ("available", "reserved"):
            raise serializers.ValidationError(f"Slot {slot.slot_number} is not available.")

        overlapping = Booking.objects.filter(
            slot=slot,
            status__in=["pending", "confirmed", "active"],
            start_time__lt=attrs["end_time"],
            end_time__gt=attrs["start_time"],
        )
        if self.instance:
            overlapping = overlapping.exclude(pk=self.instance.pk)
        if overlapping.exists():
            raise serializers.ValidationError("This slot is already booked for the selected time.")

        return attrs


class VehicleSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleSession
        fields = [
            "id", "booking", "vehicle", "slot",
            "check_in", "check_out", "duration_minutes", "overstay_minutes", "is_active",
        ]
        read_only_fields = ["id", "duration_minutes"]
