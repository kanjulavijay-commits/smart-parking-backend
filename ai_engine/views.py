from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from django.utils import timezone
from .models import AIRecommendation
from .serializers import AIRecommendationSerializer
from .recommender import recommend_slot, recommend_time
from .inference import sync_slot_statuses, predict_slot_occupancy


class AIRecommendationViewSet(viewsets.ModelViewSet):
    """CRUD + custom actions for AI recommendations."""
    serializer_class = AIRecommendationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AIRecommendation.objects.filter(
            user=self.request.user
        ).order_by("-created_at")

    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        rec = self.get_object()
        rec.was_accepted = True
        rec.save(update_fields=["was_accepted"])
        return Response({"message": "Recommendation accepted."})

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        rec = self.get_object()
        rec.was_accepted = False
        rec.save(update_fields=["was_accepted"])
        return Response({"message": "Recommendation rejected."})


class SlotRecommendationView(APIView):
    """
    POST /api/ai/recommend-slot/
    Body: { "vehicle_id", "lot_id", "start_time", "end_time" }

    Returns top-3 ranked slot recommendations with reasoning and estimated price.
    Each recommendation is saved to AIRecommendation for analytics tracking.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from parking.models import ParkingLot, Vehicle

        vehicle_id = request.data.get("vehicle_id")
        lot_id = request.data.get("lot_id")
        start_str = request.data.get("start_time")
        end_str = request.data.get("end_time")

        if not all([vehicle_id, lot_id, start_str, end_str]):
            return Response(
                {"error": "vehicle_id, lot_id, start_time, end_time are required."},
                status=400,
            )

        try:
            vehicle = Vehicle.objects.get(id=vehicle_id, owner=request.user)
            lot = ParkingLot.objects.get(id=lot_id, is_active=True)
            start_time = timezone.datetime.fromisoformat(start_str)
            end_time = timezone.datetime.fromisoformat(end_str)
        except Vehicle.DoesNotExist:
            return Response({"error": "Vehicle not found."}, status=404)
        except ParkingLot.DoesNotExist:
            return Response({"error": "Parking lot not found."}, status=404)
        except ValueError:
            return Response({"error": "Use ISO format: 2026-05-15T10:00:00"}, status=400)

        if start_time >= end_time:
            return Response({"error": "end_time must be after start_time."}, status=400)

        recommendations = recommend_slot(request.user, vehicle, lot, start_time, end_time)

        if not recommendations:
            return Response({"message": "No available slots found for the given criteria.", "results": []})

        results = []
        for rec in recommendations:
            results.append({
                "recommendation_id": str(rec.id),
                "slot_id": str(rec.recommended_slot.id),
                "slot_number": rec.recommended_slot.slot_number,
                "floor": rec.recommended_slot.zone.floor.name,
                "zone": rec.recommended_slot.zone.name,
                "zone_type": rec.recommended_slot.zone.zone_type,
                "has_ev_charger": rec.recommended_slot.has_ev_charger,
                "confidence": rec.confidence,
                "reasoning": rec.reasoning,
                "estimated_price": rec.context_data.get("estimated_price"),
                "rank": rec.context_data.get("rank"),
            })

        return Response({"count": len(results), "results": results})


class TimeRecommendationView(APIView):
    """
    POST /api/ai/recommend-time/
    Body: { "lot_id", "vehicle_id" }

    Suggests the best time window to park based on sensor occupancy history.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from parking.models import ParkingLot, Vehicle

        lot_id = request.data.get("lot_id")
        vehicle_id = request.data.get("vehicle_id")

        try:
            lot = ParkingLot.objects.get(id=lot_id, is_active=True)
            vehicle = Vehicle.objects.get(id=vehicle_id, owner=request.user)
        except (ParkingLot.DoesNotExist, Vehicle.DoesNotExist) as e:
            return Response({"error": str(e)}, status=404)

        rec = recommend_time(request.user, lot, vehicle)
        return Response({
            "recommendation_id": str(rec.id),
            "recommended_hour": rec.context_data.get("recommended_hour"),
            "reasoning": rec.reasoning,
            "hourly_occupancy": rec.context_data.get("hourly_occupancy"),
            "confidence": rec.confidence,
        })


class CameraInferenceView(APIView):
    """
    POST /api/ai/camera/{camera_id}/analyze/
    Upload a JPEG camera frame — AI analyzes all slots in the zone,
    updates their statuses in the DB, and returns confidence scores.

    Used by the edge device (Raspberry Pi / IP camera gateway).
    """
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [MultiPartParser]

    def post(self, request, camera_id):
        frame_file = request.FILES.get("frame")
        if not frame_file:
            return Response({"error": "Attach a 'frame' image file."}, status=400)

        frame_bytes = frame_file.read()

        checkpoint = request.data.get(
            "checkpoint",
            "ai_engine/checkpoints/best_model.pth",
        )

        try:
            result = sync_slot_statuses(camera_id, frame_bytes, checkpoint_path=checkpoint)
        except ValueError as e:
            return Response({"error": str(e)}, status=404)
        except Exception as e:
            return Response({"error": f"Inference failed: {str(e)}"}, status=500)

        return Response({
            "camera_id": camera_id,
            "slots_updated": result["updated"],
            "results": result["results"],
        })


class SingleSlotInferenceView(APIView):
    """
    POST /api/ai/analyze-slot/
    Upload a single cropped slot image — returns occupied/vacant prediction.
    Useful for testing the model without a full camera setup.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        import numpy as np
        from PIL import Image
        import io

        img_file = request.FILES.get("image")
        if not img_file:
            return Response({"error": "Attach an 'image' file."}, status=400)

        try:
            pil_img = Image.open(io.BytesIO(img_file.read())).convert("RGB")
            img_array = np.array(pil_img)
        except Exception:
            return Response({"error": "Cannot decode image file."}, status=400)

        checkpoint = request.data.get("checkpoint", "ai_engine/checkpoints/best_model.pth")
        result = predict_slot_occupancy(img_array, checkpoint_path=checkpoint)

        return Response({
            "is_occupied": result["is_occupied"],
            "confidence": result["confidence"],
            "raw_probability": result["raw_probability"],
            "label": "OCCUPIED" if result["is_occupied"] else "VACANT",
        })


class AIStatsView(APIView):
    """GET /api/ai/stats/ — model performance and recommendation acceptance rates."""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        from django.db.models import Count, Avg

        recs = AIRecommendation.objects.all()
        stats = recs.aggregate(
            total=Count("id"),
            accepted=Count("id", filter=__import__("django.db.models", fromlist=["Q"]).Q(was_accepted=True)),
            rejected=Count("id", filter=__import__("django.db.models", fromlist=["Q"]).Q(was_accepted=False)),
            avg_confidence=Avg("confidence"),
        )
        acceptance_rate = (
            round(stats["accepted"] / stats["total"] * 100, 1)
            if stats["total"] else 0
        )

        by_type = (
            recs.values("recommendation_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return Response({
            "total_recommendations": stats["total"],
            "accepted": stats["accepted"],
            "rejected": stats["rejected"],
            "pending": stats["total"] - stats["accepted"] - stats["rejected"],
            "acceptance_rate_pct": acceptance_rate,
            "avg_confidence": round(stats["avg_confidence"] or 0, 3),
            "by_type": list(by_type),
        })
