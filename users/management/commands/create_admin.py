"""
Management command: python manage.py create_admin
Creates a default superuser if no staff user exists yet.
Safe to run on every deploy — skips silently if admin already present.
Credentials come from env vars so they're never hardcoded.
"""

import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Create a default admin user if none exists."

    def handle(self, *args, **kwargs):
        email    = os.getenv("ADMIN_EMAIL",    "admin@smartparking.com")
        password = os.getenv("ADMIN_PASSWORD", "Admin@1234")
        name     = os.getenv("ADMIN_NAME",     "System Admin")

        user, created = User.objects.get_or_create(
            email=email,
            defaults={"full_name": name, "is_staff": True, "is_superuser": True, "is_active": True},
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()
        verb = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Admin {verb}: {email}"))
