"""
parking/models.py — Models 4-8, 13, 16, 17, 18, 19, 25
ParkingLot, ParkingFloor, ParkingZone, ParkingSlot, Vehicle,
PricingRule, SensorData, ParkingCamera, QRCode, EntryExitLog
"""

import uuid
from django.db import models
from django.conf import settings


class ParkingLot(models.Model):
    """Model 4 — A physical parking facility (building or open lot)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default="India")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    total_capacity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    operating_hours_start = models.TimeField(null=True, blank=True)
    operating_hours_end = models.TimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} — {self.city}"

    class Meta:
        db_table = "parking_lots"
        ordering = ["name"]


class ParkingFloor(models.Model):
    """Model 5 — A floor/level inside a parking lot (B1, G, L1, L2...)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name="floors")
    name = models.CharField(max_length=50)
    floor_number = models.IntegerField(default=0)
    total_slots = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.lot.name} — Floor {self.name}"

    class Meta:
        db_table = "parking_floors"
        ordering = ["lot", "floor_number"]
        unique_together = ["lot", "floor_number"]


class ParkingZone(models.Model):
    """Model 6 — A section within a floor (Zone A, Zone B, EV Zone, Handicap Zone...)."""

    STANDARD = "standard"
    EV = "ev"
    HANDICAP = "handicap"
    VIP = "vip"
    ZONE_TYPES = [
        (STANDARD, "Standard"),
        (EV, "EV Charging"),
        (HANDICAP, "Handicap"),
        (VIP, "VIP"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    floor = models.ForeignKey(ParkingFloor, on_delete=models.CASCADE, related_name="zones")
    name = models.CharField(max_length=50)
    zone_type = models.CharField(max_length=20, choices=ZONE_TYPES, default=STANDARD)
    total_slots = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.floor} — Zone {self.name}"

    class Meta:
        db_table = "parking_zones"
        ordering = ["floor", "name"]


class ParkingSlot(models.Model):
    """Model 7 — One individual parking space (e.g. A-101)."""

    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    MAINTENANCE = "maintenance"
    STATUS_CHOICES = [
        (AVAILABLE, "Available"),
        (OCCUPIED, "Occupied"),
        (RESERVED, "Reserved"),
        (MAINTENANCE, "Under Maintenance"),
    ]

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    SIZE_CHOICES = [
        (SMALL, "Small (Bike/Scooter)"),
        (MEDIUM, "Medium (Car)"),
        (LARGE, "Large (SUV/Van)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(ParkingZone, on_delete=models.CASCADE, related_name="slots")
    slot_number = models.CharField(max_length=20)
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, default=MEDIUM)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=AVAILABLE)
    floor_position_x = models.FloatField(null=True, blank=True)
    floor_position_y = models.FloatField(null=True, blank=True)
    has_ev_charger = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Slot {self.slot_number} [{self.status}]"

    class Meta:
        db_table = "parking_slots"
        ordering = ["zone", "slot_number"]
        unique_together = ["zone", "slot_number"]


class Vehicle(models.Model):
    """Model 9 — A vehicle registered by a driver (car, bike, EV, etc.)."""

    CAR = "car"
    BIKE = "bike"
    TRUCK = "truck"
    EV = "ev"
    VEHICLE_TYPES = [
        (CAR, "Car"),
        (BIKE, "Bike/Scooter"),
        (TRUCK, "Truck"),
        (EV, "Electric Vehicle"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vehicles"
    )
    license_plate = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=10, choices=VEHICLE_TYPES, default=CAR)
    make = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=50, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.license_plate} ({self.get_vehicle_type_display()})"

    class Meta:
        db_table = "vehicles"
        ordering = ["-created_at"]


class PricingRule(models.Model):
    """Model 19 — Dynamic pricing for slots (hourly, daily, peak hours, vehicle type)."""

    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"
    PRICING_TYPES = [
        (HOURLY, "Hourly"),
        (DAILY, "Daily"),
        (MONTHLY, "Monthly"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name="pricing_rules")
    name = models.CharField(max_length=100)
    pricing_type = models.CharField(max_length=10, choices=PRICING_TYPES, default=HOURLY)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    vehicle_type = models.CharField(max_length=10, null=True, blank=True)
    zone_type = models.CharField(max_length=20, null=True, blank=True)
    peak_hour_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1.0)
    peak_start_time = models.TimeField(null=True, blank=True)
    peak_end_time = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} — ₹{self.base_price}/{self.pricing_type}"

    class Meta:
        db_table = "pricing_rules"


class SensorData(models.Model):
    """Model 16 — Raw data from IoT sensors detecting slot occupancy."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slot = models.ForeignKey(ParkingSlot, on_delete=models.CASCADE, related_name="sensor_data")
    is_occupied = models.BooleanField(default=False)
    confidence_score = models.FloatField(null=True, blank=True)
    raw_value = models.FloatField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        state = "OCCUPIED" if self.is_occupied else "FREE"
        return f"Slot {self.slot.slot_number} — {state} at {self.recorded_at}"

    class Meta:
        db_table = "sensor_data"
        ordering = ["-recorded_at"]


class ParkingCamera(models.Model):
    """Model 17 — CCTV / IP cameras installed in zones for AI slot detection."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(ParkingZone, on_delete=models.CASCADE, related_name="cameras")
    name = models.CharField(max_length=100)
    stream_url = models.URLField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    installed_at = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Camera: {self.name} @ {self.zone}"

    class Meta:
        db_table = "parking_cameras"


class QRCode(models.Model):
    """Model 18 — QR code generated per booking for gate entry/exit scan."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=255, unique=True)
    qr_image = models.ImageField(upload_to="qrcodes/", blank=True, null=True)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"QR {self.token[:12]}... ({'used' if self.is_used else 'valid'})"

    class Meta:
        db_table = "qr_codes"
        ordering = ["-created_at"]


class EntryExitLog(models.Model):
    """Model 25 — Records every gate entry and exit event for a vehicle session."""

    ENTRY = "entry"
    EXIT = "exit"
    LOG_TYPES = [
        (ENTRY, "Entry"),
        (EXIT, "Exit"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="entry_exit_logs")
    slot = models.ForeignKey(ParkingSlot, on_delete=models.SET_NULL, null=True, related_name="entry_exit_logs")
    qr_code = models.ForeignKey(QRCode, on_delete=models.SET_NULL, null=True, blank=True)
    log_type = models.CharField(max_length=10, choices=LOG_TYPES)
    gate_id = models.CharField(max_length=50, blank=True)
    scanned_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.vehicle.license_plate} — {self.log_type.upper()} at {self.scanned_at}"

    class Meta:
        db_table = "entry_exit_logs"
        ordering = ["-scanned_at"]
