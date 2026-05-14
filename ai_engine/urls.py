from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AIRecommendationViewSet,
    SlotRecommendationView,
    TimeRecommendationView,
    CameraInferenceView,
    SingleSlotInferenceView,
    AIStatsView,
)

router = DefaultRouter()
router.register("recommendations", AIRecommendationViewSet, basename="recommendations")

urlpatterns = [
    path("recommend-slot/",            SlotRecommendationView.as_view(),  name="recommend-slot"),
    path("recommend-time/",            TimeRecommendationView.as_view(),  name="recommend-time"),
    path("analyze-slot/",              SingleSlotInferenceView.as_view(), name="analyze-slot"),
    path("camera/<str:camera_id>/analyze/", CameraInferenceView.as_view(), name="camera-analyze"),
    path("stats/",                     AIStatsView.as_view(),             name="ai-stats"),
    path("", include(router.urls)),
]
