from django.contrib import admin
from .models import Booking, VehicleSession


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "vehicle", "slot", "status", "start_time", "end_time", "estimated_price"]
    list_filter = ["status", "booking_type"]
    search_fields = ["user__email", "vehicle__license_plate"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(VehicleSession)
class VehicleSessionAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "slot", "check_in", "check_out", "duration_minutes", "is_active"]
    list_filter = ["is_active"]
