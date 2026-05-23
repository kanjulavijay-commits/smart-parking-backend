from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from users.models import User
from parking.models import ParkingLot, ParkingFloor, ParkingZone, ParkingSlot, Vehicle, PricingRule
from bookings.models import Booking
from payments.models import Payment, Transaction, Invoice


class PaymentSystemTests(APITestCase):
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
        self.vehicle = Vehicle.objects.create(owner=self.driver, license_plate="KA-01-MJ-9999", vehicle_type="car")
        
        # Create a booking
        self.booking = Booking.objects.create(
            user=self.driver,
            vehicle=self.vehicle,
            slot=self.slot,
            booking_type="instant",
            status="confirmed",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=2),
            estimated_price=Decimal("100.00")
        )
        
        # Create a pending payment
        self.payment = Payment.objects.create(
            booking=self.booking,
            user=self.driver,
            amount=Decimal("100.00"),
            status="pending",
            method="card"
        )
        
        self.payment_list_url = reverse("payments-list")
        self.payment_confirm_url = reverse("payments-confirm", args=[self.payment.id])
        self.payment_refund_url = reverse("payments-refund", args=[self.payment.id])
        self.payment_invoice_url = reverse("payments-invoice", args=[self.payment.id])
        self.payment_summary_url = reverse("payments-summary")
        
        self.client.force_authenticate(user=self.driver)

    def test_list_payments(self):
        """Drivers can view their transaction history in a paginated list."""
        response = self.client.get(self.payment_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(float(response.data["results"][0]["amount"]), 100.00)

    def test_confirm_payment(self):
        """Confirming payment transitions state, spawns transaction log, and prints invoice."""
        response = self.client.post(self.payment_confirm_url, {"method": "upi"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Payment confirmed.")
        self.assertIsNotNone(response.data["invoice_number"])
        
        # Verify payment transitioned
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "success")
        self.assertEqual(self.payment.method, "upi")
        
        # Verify invoice is linked
        invoice = Invoice.objects.get(payment=self.payment)
        self.assertEqual(invoice.amount, Decimal("100.00"))
        
        # Verify transaction log created
        transaction = Transaction.objects.get(payment=self.payment)
        self.assertEqual(transaction.transaction_type, "payment")
        self.assertEqual(transaction.status, "success")

    def test_refund_payment(self):
        """Refunds can be requested on processed payments."""
        # Setup payment to be successful first
        self.payment.status = "success"
        self.payment.paid_at = timezone.now()
        self.payment.save()
        
        # Create an invoice so the code won't complain (if applicable)
        Invoice.objects.create(
            payment=self.payment,
            invoice_number="INV-12345",
            amount=Decimal("100.00"),
            gst_amount=Decimal("18.00"),
            total_amount=Decimal("118.00")
        )
        
        response = self.client.post(self.payment_refund_url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Refund processed.")
        
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "refunded")
        self.assertGreater(float(self.payment.refund_amount), 0.0)

    def test_get_payment_summary(self):
        """Drivers can fetch aggregate financial summaries for their account."""
        response = self.client.get(self.payment_summary_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_spent", response.data)
        self.assertIn("completed_payments", response.data)
