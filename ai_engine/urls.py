from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AIRecommendationViewSet,
    SlotRecommendationView,
    TimeRecommendationView,
    CameraInferenceView,
    SingleSlotInferenceView,
    AIStatsView,
    RFAvailabilityView,
    LSTMForecastView,
    DatasetStatusView,
    MockCameraAnalysisView,
)

router = DefaultRouter()
router.register("recommendations", AIRecommendationViewSet, basename="recommendations")

urlpatterns = [
    # Recommender (existing)
    path("recommend-slot/",                  SlotRecommendationView.as_view(),  name="recommend-slot"),
    path("recommend-time/",                  TimeRecommendationView.as_view(),  name="recommend-time"),
    # Camera / slot inference (existing)
    path("analyze-slot/",                    SingleSlotInferenceView.as_view(), name="analyze-slot"),
    path("camera/<str:camera_id>/analyze/",  CameraInferenceView.as_view(),     name="camera-analyze"),
    # Model predictions (new)
    path("rf-predict/",                      RFAvailabilityView.as_view(),      name="rf-predict"),
    path("lstm-forecast/",                   LSTMForecastView.as_view(),        name="lstm-forecast"),
    # Admin / status (new)
    path("dataset-status/",                  DatasetStatusView.as_view(),       name="dataset-status"),
    path("mock-analyze/",                    MockCameraAnalysisView.as_view(),  name="mock-analyze"),
    path("stats/",                           AIStatsView.as_view(),             name="ai-stats"),
    path("", include(router.urls)),
]
