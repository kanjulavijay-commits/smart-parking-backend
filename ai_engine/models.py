"""
ai_engine/models.py — AIRecommendation, ModelTrainingRun, OccupancyForecast
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


class ModelTrainingRun(models.Model):
    """Records each model training run — metrics, parameters, checkpoint path."""

    CNN  = "cnn"
    RF   = "random_forest"
    LSTM = "lstm"
    MODEL_CHOICES = [
        (CNN,  "CNN (MobileNetV2)"),
        (RF,   "Random Forest"),
        (LSTM, "LSTM Forecaster"),
    ]

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_type    = models.CharField(max_length=20, choices=MODEL_CHOICES)
    started_at    = models.DateTimeField(auto_now_add=True)
    finished_at   = models.DateTimeField(null=True, blank=True)
    epochs        = models.IntegerField(null=True, blank=True)
    train_metric  = models.FloatField(null=True, blank=True)  # loss or accuracy
    val_metric    = models.FloatField(null=True, blank=True)
    checkpoint    = models.CharField(max_length=255, blank=True)
    datasets_used = models.JSONField(default=list)
    extra         = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.get_model_type_display()} run @ {self.started_at:%Y-%m-%d %H:%M}"

    class Meta:
        db_table = "ai_training_runs"
        ordering = ["-started_at"]


class OccupancyForecast(models.Model):
    """Stores LSTM-generated hourly occupancy forecasts for a parking lot."""

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lot        = models.ForeignKey(
        "parking.ParkingLot", on_delete=models.CASCADE, related_name="forecasts"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    forecast_hour_0 = models.FloatField()  # occupancy % for current_hour + 1
    forecast_hour_1 = models.FloatField()
    forecast_hour_2 = models.FloatField()
    forecast_hour_3 = models.FloatField()
    base_hour  = models.IntegerField()     # the hour this forecast was made from
    confidence = models.FloatField(default=0.8)

    def as_list(self):
        return [
            self.forecast_hour_0,
            self.forecast_hour_1,
            self.forecast_hour_2,
            self.forecast_hour_3,
        ]

    def __str__(self):
        return f"Forecast for {self.lot} from hour {self.base_hour}"

    class Meta:
        db_table = "ai_occupancy_forecasts"
        ordering = ["-created_at"]
