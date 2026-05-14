from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ParkingLotViewSet, ParkingFloorViewSet, ParkingZoneViewSet, ParkingSlotViewSet,
    VehicleViewSet, PricingRuleViewSet, SensorDataViewSet,
    ParkingCameraViewSet, EntryExitLogViewSet,
    NearestLotsView, AvailableSlotSearchView,
)

router = DefaultRouter()
router.register("lots", ParkingLotViewSet, basename="lots")
router.register("floors", ParkingFloorViewSet, basename="floors")
router.register("zones", ParkingZoneViewSet, basename="zones")
router.register("slots", ParkingSlotViewSet, basename="slots")
router.register("vehicles", VehicleViewSet, basename="vehicles")
router.register("pricing", PricingRuleViewSet, basename="pricing")
router.register("sensors", SensorDataViewSet, basename="sensors")
router.register("cameras", ParkingCameraViewSet, basename="cameras")
router.register("entry-exit-logs", EntryExitLogViewSet, basename="entry-exit-logs")

urlpatterns = [
    path("nearest/",       NearestLotsView.as_view(),       name="nearest-lots"),
    path("slots/search/",  AvailableSlotSearchView.as_view(), name="slot-search"),
    path("", include(router.urls)),
]
