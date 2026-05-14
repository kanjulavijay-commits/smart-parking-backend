from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "user", "title", "message", "category", "channel", "is_read", "read_at", "data", "created_at"]
        read_only_fields = ["id", "user", "created_at", "read_at"]
