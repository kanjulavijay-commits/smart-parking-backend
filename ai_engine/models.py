"""
ai_engine/models.py — Models 15: AIRecommendation
"""

import uuid
from django.db import models
from django.conf import settings


class AIRecommendation(models.Model):
    """Model 15 — AI-generated slot recommendation based on user history and availability."""

    SLOT = "slot"
    ROUTE = "route"
    TIME = "time"
    TYPES = [
        (SLOT, "Slot Recommendation"),
        (ROUTE, "Route Suggestion"),
        (TIME, "Time Suggestion"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_recommendations"
    )
    recommendation_type = models.CharField(max_length=10, choices=TYPES, default=SLOT)
    recommended_slot = models.ForeignKey(
        "parking.ParkingSlot", on_delete=models.SET_NULL, null=True, blank=True
    )
    recommended_lot = models.ForeignKey(
        "parking.ParkingLot", on_delete=models.SET_NULL, null=True, blank=True
    )
    confidence = models.FloatField(default=0.0)
    reasoning = models.TextField(blank=True)
    context_data = models.JSONField(default=dict)
    was_accepted = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AI Rec for {self.user} — {self.get_recommendation_type_display()} ({self.confidence:.0%})"

    class Meta:
        db_table = "ai_recommendations"
        ordering = ["-created_at"]
