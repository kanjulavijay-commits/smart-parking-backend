from rest_framework import serializers
from django.utils import timezone
from .models import Booking, VehicleSession


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = [
            "id", "user", "vehicle", "slot", "booking_type", "status",
            "start_time", "end_time", "actual_start", "actual_end",
            "estimated_price", "final_price", "cancellation_reason",
            "cancelled_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "user", "status", "actual_start", "actual_end",
            "final_price", "cancelled_at", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        if attrs["start_time"] >= attrs["end_time"]:
            raise serializers.ValidationError("end_time must be after start_time.")
        if attrs["start_time"] < timezone.now():
            raise serializers.ValidationError("Cannot book a slot in the past.")
        slot = attrs["slot"]
        if slot.status != "available":
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
