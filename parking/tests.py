from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from users.models import User
from parking.models import ParkingLot, ParkingFloor, ParkingZone, ParkingSlot, Vehicle, PricingRule


class ParkingLotTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            full_name="Admin User",
            password="AdminPassword123!",
            is_staff=True,
            is_superuser=True
        )
        self.driver = User.objects.create_user(
            email="driver@example.com",
            full_name="Driver User",
            password="DriverPassword123!"
        )
        self.lot = ParkingLot.objects.create(
            name="Seeded Test Lot",
            address="Koramangala 5th Block",
            city="Bangalore",
            state="Karnataka",
            country="India",
            latitude=12.9352,
            longitude=77.6244,
            total_capacity=10,
            is_active=True
        )
        self.lot_list_url = reverse("lots-list")
        self.lot_detail_url = reverse("lots-detail", args=[self.lot.id])
        self.availability_url = reverse("lots-availability", args=[self.lot.id])

    def test_list_lots_authenticated(self):
        """Drivers can view the list of active parking lots."""
        self.client.force_authenticate(user=self.driver)
        response = self.client.get(self.lot_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # ParkingLotListSerializer is used for lists, which might return standard fields
        self.assertGreaterEqual(len(response.data), 1)

    def test_create_lot_as_admin(self):
        """Only administrators should be allowed to create new parking lots."""
        self.client.force_authenticate(user=self.admin)
        data = {
            "name": "New Mall Parking",
            "address": "MG Road",
            "city": "Bangalore",
            "state": "Karnataka",
            "country": "India",
            "latitude": 12.9733,
            "longitude": 77.6111,
            "total_capacity": 50,
            "is_active": True
        }
        response = self.client.post(self.lot_list_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Mall Parking")

    def test_create_lot_as_driver_forbidden(self):
        """Regular drivers are forbidden from creating new parking lots."""
        self.client.force_authenticate(user=self.driver)
        data = {"name": "Unauthorized Lot"}
        response = self.client.post(self.lot_list_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class NearestLotsTests(APITestCase):
    def setUp(self):
        self.driver = User.objects.create_user(
            email="driver@example.com",
            full_name="Driver User",
            password="DriverPassword123!"
        )
        # Lot 1: In Koramangala, Bangalore (12.9352, 77.6244)
        self.lot_near = ParkingLot.objects.create(
            name="Koramangala Lot",
            address="Koramangala 5th Block",
            city="Bangalore",
            state="Karnataka",
            country="India",
            latitude=12.9352,
            longitude=77.6244,
            total_capacity=10,
            is_active=True
        )
        # Lot 2: Far away in Whitefield (12.9716, 77.7480) ~14km away
        self.lot_far = ParkingLot.objects.create(
            name="Whitefield Lot",
            address="Whitefield Main Road",
            city="Bangalore",
            state="Karnataka",
            country="India",
            latitude=12.9716,
            longitude=77.7480,
            total_capacity=10,
            is_active=True
        )
        self.nearest_url = reverse("nearest-lots")
        self.client.force_authenticate(user=self.driver)

    def test_find_nearest_lots_within_radius(self):
        """Querying coordinates should return closest parking lots within radius."""
        # Querying with latitude/longitude set near Koramangala
        response = self.client.get(
            self.nearest_url,
            {"lat": 12.9340, "lng": 77.6220, "radius": 5},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Koramangala Lot (near) should be included, Whitefield Lot (far) should be excluded
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Koramangala Lot")


class AvailableSlotSearchTests(APITestCase):
    def setUp(self):
        self.driver = User.objects.create_user(
            email="driver@example.com",
            full_name="Driver User",
            password="DriverPassword123!"
        )
        self.lot = ParkingLot.objects.create(
            name="Seeded Test Lot",
            address="Koramangala 5th Block",
            city="Bangalore",
            state="Karnataka",
            country="India",
            latitude=12.9352,
            longitude=77.6244,
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
        self.search_url = reverse("slot-search")
        self.client.force_authenticate(user=self.driver)

    def test_available_slots_search(self):
        """Searching slots with valid parameters returns open slots with pricing estimation."""
        start_time = timezone.now() + timedelta(hours=1)
        end_time = timezone.now() + timedelta(hours=3)
        response = self.client.get(
            self.search_url,
            {
                "lot_id": str(self.lot.id),
                "vehicle_type": "car",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            },
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slot_number"], "G001")
        # Price should be 50.00 base * 2 hours = 100.00 plus GST (if applicable in services)
        self.assertGreater(float(response.data["results"][0]["estimated_price"]), 0.0)


class VehicleTests(APITestCase):
    def setUp(self):
        self.driver = User.objects.create_user(
            email="driver@example.com",
            full_name="Driver User",
            password="DriverPassword123!"
        )
        self.client.force_authenticate(user=self.driver)
        self.vehicle_list_url = reverse("vehicles-list")

    def test_add_driver_vehicle(self):
        """Drivers can add their own vehicles to their profile."""
        data = {
            "license_plate": "KA-01-MJ-9999",
            "vehicle_type": "car",
            "nickname": "Black Beast",
            "is_default": True
        }
        response = self.client.post(self.vehicle_list_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["license_plate"], "KA-01-MJ-9999")
        
        # Verify in DB
        vehicle = Vehicle.objects.get(license_plate="KA-01-MJ-9999")
        self.assertEqual(vehicle.owner, self.driver)
        self.assertTrue(vehicle.is_default)

    def test_set_default_vehicle(self):
        """Setting a primary vehicle clears defaults from other vehicles."""
        vehicle1 = Vehicle.objects.create(
            owner=self.driver,
            license_plate="KA-01-AA-1111",
            vehicle_type="car",
            is_default=True
        )
        vehicle2 = Vehicle.objects.create(
            owner=self.driver,
            license_plate="KA-01-BB-2222",
            vehicle_type="car",
            is_default=False
        )
        set_default_url = reverse("vehicles-set-default", args=[vehicle2.id])
        response = self.client.post(set_default_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh from DB
        vehicle1.refresh_from_db()
        vehicle2.refresh_from_db()
        self.assertFalse(vehicle1.is_default)
        self.assertTrue(vehicle2.is_default)
