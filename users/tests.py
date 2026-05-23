from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from users.models import User, Role, Permission, SupportTicket


class UserRegistrationTests(APITestCase):
    def setUp(self):
        self.register_url = reverse("register")

    def test_successful_registration(self):
        """Drivers should be able to sign up with a complete profile."""
        data = {
            "email": "driver@example.com",
            "full_name": "Test Driver",
            "phone": "+919876543210",
            "password": "SecurePassword123!",
            "password_confirm": "SecurePassword123!"
        }
        response = self.client.post(self.register_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("message", response.data)
        self.assertEqual(response.data["email"], "driver@example.com")
        
        # Verify user is created in database
        user = User.objects.get(email="driver@example.com")
        self.assertEqual(user.full_name, "Test Driver")
        self.assertFalse(user.is_email_verified) # Starts unverified

    def test_registration_password_mismatch(self):
        """Registration should fail if passwords do not match."""
        data = {
            "email": "driver@example.com",
            "full_name": "Test Driver",
            "phone": "+919876543210",
            "password": "SecurePassword123!",
            "password_confirm": "DifferentPassword123!"
        }
        response = self.client.post(self.register_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_registration_duplicate_email(self):
        """Users cannot register with an already registered email."""
        User.objects.create_user(
            email="existing@example.com",
            full_name="Existing User",
            password="SecurePassword123!"
        )
        data = {
            "email": "existing@example.com",
            "full_name": "New User",
            "password": "NewPassword123!",
            "password_confirm": "NewPassword123!"
        }
        response = self.client.post(self.register_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)


class UserLoginTests(APITestCase):
    def setUp(self):
        self.login_url = reverse("login")
        self.user = User.objects.create_user(
            email="driver@example.com",
            full_name="John Doe",
            password="SecurePassword123!"
        )

    def test_successful_login(self):
        """Login should return access + refresh tokens and user profile."""
        data = {
            "email": "driver@example.com",
            "password": "SecurePassword123!"
        }
        response = self.client.post(self.login_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["email"], "driver@example.com")

    def test_login_incorrect_password(self):
        """Login should fail if user supplies wrong password."""
        data = {
            "email": "driver@example.com",
            "password": "WrongPassword123!"
        }
        response = self.client.post(self.login_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserProfileTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="driver@example.com",
            full_name="John Doe",
            password="SecurePassword123!"
        )
        self.client.force_authenticate(user=self.user)
        self.me_url = reverse("users-me")
        self.update_url = reverse("users-update-me")
        self.change_password_url = reverse("users-change-password")

    def test_get_own_profile(self):
        """Authenticated users can retrieve their own profile details."""
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "driver@example.com")
        self.assertEqual(response.data["full_name"], "John Doe")

    def test_update_own_profile(self):
        """Authenticated users can partially update their profile."""
        data = {
            "full_name": "John Updated",
            "phone": "+911111111111"
        }
        response = self.client.patch(self.update_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["full_name"], "John Updated")
        
        # Verify DB is updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "John Updated")
        self.assertEqual(self.user.phone, "+911111111111")

    def test_change_password(self):
        """Users can update their password if their old password is valid."""
        data = {
            "old_password": "SecurePassword123!",
            "new_password": "NewSecurePassword456!"
        }
        response = self.client.post(self.change_password_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        
        # Verify login with new password works
        self.client.force_authenticate(user=None) # clear auth
        login_url = reverse("login")
        login_data = {
            "email": "driver@example.com",
            "password": "NewSecurePassword456!"
        }
        login_response = self.client.post(login_url, login_data, format="json")
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)


class SupportTicketTests(APITestCase):
    def setUp(self):
        self.driver = User.objects.create_user(
            email="driver@example.com",
            full_name="Driver User",
            password="Password123!"
        )
        self.operator = User.objects.create_user(
            email="operator@example.com",
            full_name="Operator User",
            password="Password123!",
            is_staff=True
        )
        self.support_list_url = reverse("support-list")

    def test_create_support_ticket(self):
        """Drivers can submit support tickets."""
        self.client.force_authenticate(user=self.driver)
        data = {
            "subject": "App Crash on payment screen",
            "description": "Whenever I tap 'Pay' the app crashes.",
            "priority": "high"
        }
        response = self.client.post(self.support_list_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["subject"], "App Crash on payment screen")
        
        # Verify in DB
        ticket = SupportTicket.objects.get(subject="App Crash on payment screen")
        self.assertEqual(ticket.user, self.driver)
        self.assertEqual(ticket.priority, "high")

    def test_driver_only_sees_own_tickets(self):
        """Regular drivers should only see support tickets they created."""
        other_driver = User.objects.create_user(
            email="other@example.com",
            full_name="Other Driver",
            password="Password123!"
        )
        # Create ticket for driver
        SupportTicket.objects.create(user=self.driver, subject="Ticket 1", description="Help")
        # Create ticket for other_driver
        SupportTicket.objects.create(user=other_driver, subject="Ticket 2", description="Help")

        self.client.force_authenticate(user=self.driver)
        response = self.client.get(self.support_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only list 1 ticket (Ticket 1) in paginated results
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["subject"], "Ticket 1")

    def test_staff_sees_all_tickets(self):
        """Staff members should be able to view tickets from all users."""
        SupportTicket.objects.create(user=self.driver, subject="Ticket 1", description="Help")
        self.client.force_authenticate(user=self.operator)
        response = self.client.get(self.support_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["subject"], "Ticket 1")
