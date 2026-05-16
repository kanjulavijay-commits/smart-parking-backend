from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from .models import (
    ParkingLot, ParkingFloor, ParkingZone, ParkingSlot,
    Vehicle, PricingRule, SensorData, ParkingCamera, QRCode, EntryExitLog,
)
from .serializers import (
    ParkingLotSerializer, ParkingLotListSerializer, ParkingFloorSerializer,
    ParkingZoneSerializer, ParkingSlotSerializer, VehicleSerializer,
    PricingRuleSerializer, SensorDataSerializer, ParkingCameraSerializer,
    QRCodeSerializer, EntryExitLogSerializer,
)
from .services import calculate_price, get_lot_availability_summary, find_nearest_lots


class ParkingLotViewSet(viewsets.ModelViewSet):
    queryset = ParkingLot.objects.prefetch_related("floors__zones__slots").filter(is_active=True)
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "city", "address"]
    ordering_fields = ["name", "created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return ParkingLotListSerializer
        return ParkingLotSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=["get"], url_path="availability")
    def availability(self, request, pk=None):
        """GET /api/parking/lots/{id}/availability/ — full real-time availability map."""
        lot = self.get_object()
        return Response(get_lot_availability_summary(lot))

    @action(detail=True, methods=["post"], url_path="calculate-price")
    def calculate_price_view(self, request, pk=None):
        """
        POST /api/parking/lots/{id}/calculate-price/
        Body: { "slot_id", "vehicle_type", "start_time", "end_time" }
        Returns: full price breakdown including GST.
        """
        lot = self.get_object()
        slot_id = request.data.get("slot_id")
        vehicle_type = request.data.get("vehicle_type", "car")
        start_str = request.data.get("start_time")
        end_str = request.data.get("end_time")

        if not all([slot_id, start_str, end_str]):
            return Response(
                {"error": "slot_id, start_time, and end_time are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            slot = ParkingSlot.objects.get(id=slot_id, zone__floor__lot=lot)
        except ParkingSlot.DoesNotExist:
            return Response({"error": "Slot not found in this lot."}, status=404)

        try:
            start_time = timezone.datetime.fromisoformat(start_str)
            end_time = timezone.datetime.fromisoformat(end_str)
        except ValueError:
            return Response({"error": "Use ISO format: 2026-05-15T10:00:00"}, status=400)

        if start_time >= end_time:
            return Response({"error": "end_time must be after start_time."}, status=400)

        breakdown = calculate_price(slot, vehicle_type, start_time, end_time)
        return Response(breakdown)

    @action(detail=True, methods=["get"], url_path="floor-map")
    def floor_map(self, request, pk=None):
        """
        GET /api/parking/lots/{id}/floor-map/?floor_number=1
        Returns every slot in a floor with position coordinates — used to render
        the interactive parking map on the frontend.
        """
        lot = self.get_object()
        floor_number = request.query_params.get("floor_number", 0)

        try:
            floor = lot.floors.get(floor_number=int(floor_number), is_active=True)
        except ParkingFloor.DoesNotExist:
            return Response({"error": "Floor not found."}, status=404)

        map_data = {"floor": floor.name, "floor_number": floor.floor_number, "zones": []}
        for zone in floor.zones.filter(is_active=True).order_by("name"):
            slots = []
            for slot in zone.slots.filter(is_active=True).order_by("slot_number"):
                slots.append({
                    "id": str(slot.id),
                    "slot_number": slot.slot_number,
                    "status": slot.status,
                    "size": slot.size,
                    "has_ev_charger": slot.has_ev_charger,
                    "x": slot.floor_position_x,
                    "y": slot.floor_position_y,
                })
            map_data["zones"].append({
                "zone_id": str(zone.id),
                "zone_name": zone.name,
                "zone_type": zone.zone_type,
                "slots": slots,
            })
        return Response(map_data)


class NearestLotsView(APIView):
    """
    GET /api/parking/nearest/?lat=12.9716&lng=77.5946&radius=5
    Returns nearby lots sorted by distance. Used for the map-based lot picker.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            lat = float(request.query_params.get("lat", 0))
            lng = float(request.query_params.get("lng", 0))
            radius = float(request.query_params.get("radius", 10))
        except (TypeError, ValueError):
            return Response({"error": "lat, lng must be valid numbers."}, status=400)

        if lat == 0 and lng == 0:
            return Response({"error": "lat and lng are required."}, status=400)

        lots = find_nearest_lots(lat, lng, radius_km=radius)
        return Response({"count": len(lots), "results": lots})


class AvailableSlotSearchView(APIView):
    """
    GET /api/parking/slots/search/?lot_id=X&vehicle_type=car&start_time=...&end_time=...
    Finds available slots for a given lot + time window.
    Excludes slots that have confirmed/active bookings overlapping the window.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        lot_id = request.query_params.get("lot_id")
        vehicle_type = request.query_params.get("vehicle_type", "car")
        start_str = request.query_params.get("start_time")
        end_str = request.query_params.get("end_time")
        zone_type = request.query_params.get("zone_type")
        ev_only = request.query_params.get("ev_only") == "true"

        if not all([lot_id, start_str, end_str]):
            return Response({"error": "lot_id, start_time, end_time are required."}, status=400)

        try:
            start_time = timezone.datetime.fromisoformat(start_str)
            end_time = timezone.datetime.fromisoformat(end_str)
        except ValueError:
            return Response({"error": "Use ISO format: 2026-05-15T10:00:00"}, status=400)

        # Map vehicle_type to slot size
        size_map = {"bike": "small", "car": "medium", "ev": "medium", "truck": "large"}
        slot_size = size_map.get(vehicle_type, "medium")

        # Find slots that have no overlapping bookings
        from bookings.models import Booking
        booked_slot_ids = Booking.objects.filter(
            slot__zone__floor__lot_id=lot_id,
            status__in=["pending", "confirmed", "active"],
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).values_list("slot_id", flat=True)

        slots_qs = ParkingSlot.objects.filter(
            zone__floor__lot_id=lot_id,
            status="available",
            is_active=True,
            size=slot_size,
        ).exclude(id__in=booked_slot_ids).select_related("zone__floor")

        if zone_type:
            slots_qs = slots_qs.filter(zone__zone_type=zone_type)
        if ev_only:
            slots_qs = slots_qs.filter(has_ev_charger=True)

        results = []
        for slot in slots_qs[:50]:  # cap at 50 results
            price_info = calculate_price(slot, vehicle_type, start_time, end_time)
            results.append({
                "slot_id": str(slot.id),
                "slot_number": slot.slot_number,
                "zone": slot.zone.name,
                "zone_type": slot.zone.zone_type,
                "floor": slot.zone.floor.name,
                "size": slot.size,
                "has_ev_charger": slot.has_ev_charger,
                "estimated_price": price_info["total"],
            })

        results.sort(key=lambda x: x["estimated_price"])
        return Response({"count": len(results), "results": results})


class ParkingFloorViewSet(viewsets.ModelViewSet):
    queryset = ParkingFloor.objects.select_related("lot").prefetch_related("zones")
    serializer_class = ParkingFloorSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]


class ParkingZoneViewSet(viewsets.ModelViewSet):
    queryset = ParkingZone.objects.select_related("floor__lot").prefetch_related("slots")
    serializer_class = ParkingZoneSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]


class ParkingSlotViewSet(viewsets.ModelViewSet):
    serializer_class = ParkingSlotSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "size", "has_ev_charger", "zone"]

    def get_queryset(self):
        qs = ParkingSlot.objects.select_related("zone__floor__lot").all()
        lot_id = self.request.query_params.get("lot")
        if lot_id:
            qs = qs.filter(zone__floor__lot_id=lot_id)
        return qs

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]


class VehicleViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Vehicle.objects.select_related("owner").all()
        return Vehicle.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        """POST /api/parking/vehicles/{id}/set-default/ — mark as primary vehicle."""
        vehicle = self.get_object()
        Vehicle.objects.filter(owner=request.user).update(is_default=False)
        vehicle.is_default = True
        vehicle.save()
        return Response({"message": f"{vehicle.license_plate} is now your default vehicle."})


class PricingRuleViewSet(viewsets.ModelViewSet):
    queryset = PricingRule.objects.select_related("lot").filter(is_active=True)
    serializer_class = PricingRuleSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]


class SensorDataViewSet(viewsets.ModelViewSet):
    queryset = SensorData.objects.select_related("slot").order_by("-recorded_at")
    serializer_class = SensorDataSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        """When a sensor fires, auto-update the slot status."""
        instance = serializer.save()
        slot = instance.slot
        slot.status = "occupied" if instance.is_occupied else "available"
        slot.save(update_fields=["status"])


class ParkingCameraViewSet(viewsets.ModelViewSet):
    queryset = ParkingCamera.objects.select_related("zone").all()
    serializer_class = ParkingCameraSerializer
    permission_classes = [permissions.IsAdminUser]


class EntryExitLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EntryExitLog.objects.select_related("vehicle", "slot").all()
    serializer_class = EntryExitLogSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["log_type", "vehicle"]
