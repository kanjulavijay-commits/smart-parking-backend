from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from users.models import User
from parking.models import ParkingLot, ParkingFloor, ParkingZone, ParkingSlot, Vehicle, PricingRule, QRCode, EntryExitLog
from bookings.models import Booking, VehicleSession


class BookingSystemTests(APITestCase):
    def setUp(self):
        self.driver = User.objects.create_user(
            email="driver@example.com",
            full_name="Driver User",
            password="DriverPassword123!"
        )
        self.lot = ParkingLot.objects.create(
            name="Phoenix Mall",
            address="Whitefield Main Road",
            city="Bangalore",
            state="Karnataka",
            country="India",
            latitude=12.9716,
            longitude=77.7480,
            total_capacity=10,
            is_active=True
        )
        self.floor = ParkingFloor.objects.create(
            lot=self.lot,
            floor_number=0,
            name="Ground",
            total_slots=10
        )
        self.zone = ParkingZone.objects.create(
            floor=self.floor,
            name="Zone A",
            zone_type="standard",
            total_slots=10
        )
        self.slot = ParkingSlot.objects.create(
            zone=self.zone,
            slot_number="G001",
            size="medium",
            status="available",
            is_active=True
        )
        self.pricing = PricingRule.objects.create(
            lot=self.lot,
            name="Standard Hourly",
            pricing_type="hourly",
            base_price="50.00",
            peak_hour_multiplier="1.0"
        )
        self.vehicle = Vehicle.objects.create(
            owner=self.driver,
            license_plate="KA-01-MJ-9999",
            vehicle_type="car",
            is_default=True
        )
        self.booking_list_url = reverse("bookings-list")
        self.client.force_authenticate(user=self.driver)

    def test_create_instant_booking_successful(self):
        """Drivers can book a slot instantly for a valid time window."""
        start_time = timezone.now() + timedelta(minutes=10)
        end_time = timezone.now() + timedelta(hours=2)
        
        data = {
            "vehicle": str(self.vehicle.id),
            "slot": str(self.slot.id),
            "booking_type": "instant",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        response = self.client.post(self.booking_list_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "confirmed")
        
        # Verify slot is reserved
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.status, "reserved")
        
        # Verify a QR code and EntryExitLog are generated
        booking = Booking.objects.get(id=response.data["id"])
        self.assertIsNotNone(booking.estimated_price)
        
        log = EntryExitLog.objects.filter(vehicle=self.vehicle, slot=self.slot).first()
        self.assertIsNotNone(log)
        self.assertIsNotNone(log.qr_code)

    def test_cancel_booking(self):
        """Drivers can cancel a confirmed booking, restoring slot availability."""
        start_time = timezone.now() + timedelta(minutes=10)
        end_time = timezone.now() + timedelta(hours=2)
        
        booking = Booking.objects.create(
            user=self.driver,
            vehicle=self.vehicle,
            slot=self.slot,
            booking_type="instant",
            status="confirmed",
            start_time=start_time,
            end_time=end_time,
            estimated_price=Decimal("100.00")
        )
        self.slot.status = "reserved"
        self.slot.save()
        
        cancel_url = reverse("bookings-cancel", args=[booking.id])
        response = self.client.post(cancel_url, {"reason": "Plan changed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "cancelled")
        
        # Verify slot is freed
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.status, "available")


class GateScanTests(APITestCase):
    def setUp(self):
        self.driver = User.objects.create_user(
            email="driver@example.com",
            full_name="Driver User",
            password="DriverPassword123!"
        )
        self.lot = ParkingLot.objects.create(
            name="Phoenix Mall",
            latitude=12.9716,
            longitude=77.7480,
            is_active=True
        )
        self.floor = ParkingFloor.objects.create(lot=self.lot, floor_number=0, name="Ground")
        self.zone = ParkingZone.objects.create(floor=self.floor, name="Zone A", zone_type="standard")
        self.slot = ParkingSlot.objects.create(zone=self.zone, slot_number="G001", size="medium", status="available")
        self.pricing = PricingRule.objects.create(lot=self.lot, name="Standard", base_price="50.00", peak_hour_multiplier="1.0")
        self.vehicle = Vehicle.objects.create(owner=self.driver, license_plate="KA-01-MJ-9999", vehicle_type="car")
        
        # Create a confirmed booking
        self.start_time = timezone.now() - timedelta(minutes=5)
        self.end_time = timezone.now() + timedelta(hours=2)
        
        self.booking = Booking.objects.create(
            user=self.driver,
            vehicle=self.vehicle,
            slot=self.slot,
            booking_type="instant",
            status="confirmed",
            start_time=self.start_time,
            end_time=self.end_time,
            estimated_price=Decimal("100.00")
        )
        self.slot.status = "reserved"
        self.slot.save()
        
        # Set up a valid QR code
        self.qr_code = QRCode.objects.create(
            token="valid-token-12345",
            expires_at=self.end_time
        )
        
        # Pre-register entry log
        self.log = EntryExitLog.objects.create(
            vehicle=self.vehicle,
            slot=self.slot,
            qr_code=self.qr_code,
            log_type="entry",
            gate_id="PENDING"
        )
        
        self.scan_url = reverse("gate-scan")
        self.client.force_authenticate(user=self.driver)

    def test_gate_scan_entry_opens_gate(self):
        """Scanning a valid QR code on entry transitions booking to active and checks in vehicle."""
        data = {
            "token": "valid-token-12345",
            "gate_id": "GATE-ENTRY-1",
            "scan_type": "entry"
        }
        response = self.client.post(self.scan_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["action"], "OPEN")
        self.assertIn("Welcome", response.data["message"])
        
        # Verify booking is active and slot is occupied
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "active")
        
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.status, "occupied")
        
        # Verify vehicle session is created
        session = VehicleSession.objects.filter(booking=self.booking).first()
        self.assertIsNotNone(session)
        self.assertTrue(session.is_active)
        self.assertIsNotNone(session.check_in)

    def test_gate_scan_exit_completes_booking(self):
        """Scanning a valid QR code on exit transitions booking to completed and checks out vehicle."""
        # Set booking to active first (already checked in)
        self.booking.status = "active"
        self.booking.actual_start = timezone.now() - timedelta(hours=1)
        self.booking.save()
        self.slot.status = "occupied"
        self.slot.save()
        
        session = VehicleSession.objects.create(
            booking=self.booking,
            vehicle=self.vehicle,
            slot=self.slot,
            check_in=timezone.now() - timedelta(hours=1),
            is_active=True
        )
        
        data = {
            "token": "valid-token-12345",
            "gate_id": "GATE-EXIT-1",
            "scan_type": "exit"
        }
        response = self.client.post(self.scan_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["action"], "OPEN")
        self.assertIn("Goodbye", response.data["message"])
        
        # Verify booking is completed and slot is available
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "completed")
        self.assertIsNotNone(self.booking.final_price)
        
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.status, "available")
        
        # Verify session is inactive and checked out
        session.refresh_from_db()
        self.assertFalse(session.is_active)
        self.assertIsNotNone(session.check_out)

    def test_gate_scan_expired_token_denies_gate(self):
        """An expired QR code is denied at the gate."""
        self.qr_code.expires_at = timezone.now() - timedelta(minutes=1)
        self.qr_code.save()
        
        data = {
            "token": "valid-token-12345",
            "gate_id": "GATE-ENTRY-1",
            "scan_type": "entry"
        }
        response = self.client.post(self.scan_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["action"], "DENY")
        self.assertIn("expired", response.data["message"])
