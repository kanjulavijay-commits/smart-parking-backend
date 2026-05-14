from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BookingViewSet, VehicleSessionViewSet,
    GateScanView, GateStatusView, OverstayCheckView,
)

router = DefaultRouter()
router.register("sessions", VehicleSessionViewSet, basename="sessions")
router.register("", BookingViewSet, basename="bookings")

urlpatterns = [
    path("gate/scan/",            GateScanView.as_view(),      name="gate-scan"),
    path("gate/status/",          GateStatusView.as_view(),    name="gate-status"),
    path("gate/check-overstays/", OverstayCheckView.as_view(), name="check-overstays"),
    path("", include(router.urls)),
]
