"""
Management command: python manage.py check_overstays
Run this every minute via cron/Celery in production to detect overstays.
"""

from django.core.management.base import BaseCommand
from bookings.gate import detect_overstays


class Command(BaseCommand):
    help = "Scan for overstayed bookings and send alerts."

    def handle(self, *args, **kwargs):
        count = detect_overstays()
        if count:
            self.stdout.write(self.style.WARNING(f"Overstay alerts sent: {count}"))
        else:
            self.stdout.write(self.style.SUCCESS("No overstays detected."))
