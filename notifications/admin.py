from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "category", "channel", "is_read", "created_at"]
    list_filter = ["category", "channel", "is_read"]
    search_fields = ["user__email", "title"]
