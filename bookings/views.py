from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from .models import Booking, VehicleSession
from .serializers import BookingSerializer, VehicleSessionSerializer
from .services import create_booking, cancel_booking, check_in_booking, check_out_booking
from .gate import scan_qr, detect_overstays
from parking.models import ParkingSlot, Vehicle


class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "booking_type"]
    ordering_fields = ["start_time", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Booking.objects.select_related(
                "user", "vehicle", "slot__zone__floor__lot"
            ).all()
        return Booking.objects.filter(user=self.request.user).select_related(
            "vehicle", "slot__zone__floor__lot"
        )

    def perform_create(self, serializer):
        # Validate manually first so we can pass validated objects to service
        validated = serializer.validated_data
        booking = create_booking(
            user=self.request.user,
            vehicle=validated["vehicle"],
            slot=validated["slot"],
            booking_type=validated.get("booking_type", "instant"),
            start_time=validated["start_time"],
            end_time=validated["end_time"],
        )
        serializer.instance = booking

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            BookingSerializer(serializer.instance).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="upcoming")
    def upcoming(self, request):
        """GET /api/bookings/upcoming/ — confirmed bookings in the future."""
        qs = self.get_queryset().filter(
            status__in=["confirmed", "active"],
            end_time__gte=timezone.now(),
        ).order_by("start_time")
        return Response(BookingSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="history")
    def history(self, request):
        """GET /api/bookings/history/ — completed and cancelled bookings."""
        qs = self.get_queryset().filter(
            status__in=["completed", "cancelled", "no_show"]
        ).order_by("-created_at")
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(BookingSerializer(page, many=True).data)
        return Response(BookingSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """POST /api/bookings/{id}/cancel/ — cancel a booking."""
        booking = self.get_object()
        try:
            booking = cancel_booking(booking, reason=request.data.get("reason", ""))
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BookingSerializer(booking).data)

    @action(detail=True, methods=["post"], url_path="check-in")
    def check_in(self, request, pk=None):
        """POST /api/bookings/{id}/check-in/ — mark vehicle arrival at the gate."""
        booking = self.get_object()
        try:
            session = check_in_booking(booking)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)
        return Response({
            "message": "Checked in successfully.",
            "session_id": str(session.id),
            "slot": booking.slot.slot_number,
            "check_in": session.check_in,
        })

    @action(detail=True, methods=["post"], url_path="check-out")
    def check_out(self, request, pk=None):
        """POST /api/bookings/{id}/check-out/ — mark vehicle departure."""
        booking = self.get_object()
        try:
            result = check_out_booking(booking)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)
        return Response({
            "message": "Checked out successfully.",
            "duration_minutes": result["session"].duration_minutes,
            "overstay_minutes": result["session"].overstay_minutes,
            "final_price": str(result["final_price"]),
            "price_breakdown": result["price_breakdown"],
        })

    @action(detail=True, methods=["get"], url_path="qr-code")
    def qr_code(self, request, pk=None):
        """GET /api/bookings/{id}/qr-code/ — retrieve QR code for gate scan."""
        booking = self.get_object()
        from parking.models import EntryExitLog
        log = EntryExitLog.objects.filter(
            vehicle=booking.vehicle,
            slot=booking.slot,
            qr_code__isnull=False,
        ).select_related("qr_code").first()

        if not log or not log.qr_code:
            return Response({"error": "QR code not found for this booking."}, status=404)

        qr = log.qr_code
        qr_url = request.build_absolute_uri(qr.qr_image.url) if qr.qr_image else None
        return Response({
            "token": qr.token,
            "qr_image_url": qr_url,
            "expires_at": qr.expires_at,
            "is_used": qr.is_used,
        })

    @action(detail=True, methods=["get"], url_path="receipt")
    def receipt(self, request, pk=None):
        """GET /api/bookings/{id}/receipt/ — full booking receipt after completion."""
        booking = self.get_object()
        if booking.status != "completed":
            return Response({"error": "Receipt is only available for completed bookings."}, status=400)

        session = getattr(booking, "session", None)
        return Response({
            "booking_id": str(booking.id),
            "slot": booking.slot.slot_number,
            "lot": booking.slot.zone.floor.lot.name,
            "vehicle": booking.vehicle.license_plate,
            "check_in": session.check_in if session else booking.actual_start,
            "check_out": session.check_out if session else booking.actual_end,
            "duration_minutes": session.duration_minutes if session else None,
            "overstay_minutes": session.overstay_minutes if session else 0,
            "estimated_price": str(booking.estimated_price),
            "final_price": str(booking.final_price),
            "status": booking.status,
        })


class GateScanView(APIView):
    """
    POST /api/bookings/gate/scan/
    Called by the physical gate terminal when a driver scans their QR code.
    Returns OPEN or DENY with a human-readable message for the gate display.

    Body:
      { "token": "...", "gate_id": "GATE-A1", "scan_type": "entry" | "exit" }

    No user auth needed here — the gate terminal uses its own API key in prod.
    For now we allow any authenticated user to simulate a scan.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        token = request.data.get("token")
        gate_id = request.data.get("gate_id", "UNKNOWN")
        scan_type = request.data.get("scan_type", "entry")

        if not token:
            return Response({"error": "token is required."}, status=400)
        if scan_type not in ("entry", "exit"):
            return Response({"error": "scan_type must be 'entry' or 'exit'."}, status=400)

        result = scan_qr(token=token, gate_id=gate_id, scan_type=scan_type)
        http_status = 200 if result["action"] == "OPEN" else 403
        return Response(result, status=http_status)


class GateStatusView(APIView):
    """
    GET /api/bookings/gate/status/?lot_id=X
    Returns live occupancy + active sessions for a gate operator's dashboard.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from parking.models import ParkingSlot, ParkingLot
        lot_id = request.query_params.get("lot_id")

        sessions_qs = VehicleSession.objects.filter(is_active=True).select_related(
            "vehicle", "slot__zone__floor__lot", "booking__user"
        )
        if lot_id:
            sessions_qs = sessions_qs.filter(slot__zone__floor__lot_id=lot_id)

        active_sessions = []
        for s in sessions_qs:
            duration = int((timezone.now() - s.check_in).total_seconds() / 60) if s.check_in else 0
            active_sessions.append({
                "session_id": str(s.id),
                "vehicle": s.vehicle.license_plate,
                "slot": s.slot.slot_number,
                "floor": s.slot.zone.floor.name,
                "check_in": s.check_in,
                "duration_minutes": duration,
                "overstay_minutes": s.overstay_minutes,
                "user": s.booking.user.full_name,
            })

        slot_stats = {}
        if lot_id:
            slots = ParkingSlot.objects.filter(zone__floor__lot_id=lot_id, is_active=True)
            slot_stats = {
                "total": slots.count(),
                "available": slots.filter(status="available").count(),
                "occupied": slots.filter(status="occupied").count(),
                "reserved": slots.filter(status="reserved").count(),
            }

        return Response({
            "active_sessions": len(active_sessions),
            "slot_stats": slot_stats,
            "sessions": active_sessions,
        })


class OverstayCheckView(APIView):
    """POST /api/bookings/gate/check-overstays/ — manually trigger overstay scan (admin only)."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        count = detect_overstays()
        return Response({"overstay_alerts_sent": count})


class VehicleSessionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VehicleSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return VehicleSession.objects.select_related(
                "booking__user", "vehicle", "slot"
            ).all()
        return VehicleSession.objects.filter(
            booking__user=self.request.user
        ).select_related("vehicle", "slot")
