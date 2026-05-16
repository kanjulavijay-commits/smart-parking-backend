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

        include_comparison = request.data.get("include_comparison") == "true" or request.GET.get("comparison") == "true"

        try:
            result = sync_slot_statuses(
                camera_id, 
                frame_bytes, 
                checkpoint_path=checkpoint,
                include_comparison=include_comparison
            )
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


class MockCameraAnalysisView(APIView):
    """
    POST /api/ai/mock-analyze/
    Simulates a live camera feed by picking random images from the dataset
    and running the 3-model comparison on all slots.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        import random
        from parking.models import ParkingSlot, ParkingLot
        
        lot_id = request.data.get("lot_id")
        lot = ParkingLot.objects.filter(id=lot_id).first() if lot_id else ParkingLot.objects.first()
        
        if not lot:
            return Response({"error": "No parking lot found."}, status=404)

        # 1. Get all slots for this lot
        slots = ParkingSlot.objects.filter(zone__floor__lot=lot, is_active=True)
        
        # 2. Simulate AI results by picking random images from our 12-dataset library
        # In a real system, we'd have a single frame. Here we simulate slot-by-slot.
        dataset_path = "data_library/combined_master/val"
        results = []
        
        # Check if dataset exists
        if not os.path.exists(dataset_path):
            return Response({"error": "Dataset library not found. Run Part 1 first."}, status=400)

        for slot in slots:
            # Pick a random label to simulate
            label = random.choice(["occupied", "vacant"])
            folder = os.path.join(dataset_path, label)
            files = os.listdir(folder)
            if not files: continue
            
            img_path = os.path.join(folder, random.choice(files))
            
            # Load and predict
            from PIL import Image
            import numpy as np
            pil_img = Image.open(img_path).convert("RGB")
            img_array = np.array(pil_img)
            
            # Run the 3-model comparison!
            prediction = predict_slot_occupancy(img_array, include_comparison=True)
            prediction["slot_id"] = str(slot.id)
            prediction["slot_number"] = slot.slot_number
            results.append(prediction)
            
            # Update slot status in DB to match AI
            new_status = "occupied" if prediction["is_occupied"] else "available"
            if slot.status not in ("reserved", "maintenance"):
                slot.status = new_status
                slot.save(update_fields=["status", "updated_at"])

        return Response({
            "lot_name": lot.name,
            "count": len(results),
            "results": results,
            "timestamp": timezone.now()
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


# ─── Random Forest Availability Prediction ────────────────────────────────────

class RFAvailabilityView(APIView):
    """
    GET /api/ai/rf-predict/?lot_id=<id>&hour=<0-23>&day=<0-6>

    Uses the trained Random Forest model to predict parking availability
    for a given lot, hour of day, and day of week.

    day: 0=Monday … 6=Sunday
    Returns: { "status": "high/medium/low", "probability": 0.0-1.0, ... }
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from parking.models import ParkingLot
        from ai_engine.ml_models.random_forest import ParkingAvailabilityRF
        from django.utils import timezone

        lot_id = request.query_params.get("lot_id")
        try:
            hour = int(request.query_params.get("hour", timezone.now().hour))
            day  = int(request.query_params.get("day",  timezone.now().weekday()))
        except (ValueError, TypeError):
            return Response({"error": "hour and day must be integers."}, status=400)

        if not (0 <= hour <= 23):
            return Response({"error": "hour must be 0-23."}, status=400)
        if not (0 <= day <= 6):
            return Response({"error": "day must be 0-6 (Mon-Sun)."}, status=400)

        if not ParkingAvailabilityRF.is_trained():
            return Response({
                "error": "Random Forest model not trained yet.",
                "hint": "Run: python manage.py train_random_forest",
            }, status=503)

        try:
            lot = ParkingLot.objects.get(id=lot_id, is_active=True) if lot_id else None
        except ParkingLot.DoesNotExist:
            return Response({"error": "Parking lot not found."}, status=404)

        rf = ParkingAvailabilityRF.load()
        month = timezone.now().month

        lot_name  = lot.name if lot else "Main Lot"
        zone_name = request.query_params.get("zone", "Zone A")

        prediction = rf.predict_availability(
            hour=hour,
            day_of_week=day,
            month=month,
            lot_name=lot_name,
            zone_name=zone_name,
        )

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        return Response({
            "lot_id":       lot_id,
            "lot_name":     lot_name,
            "zone":         zone_name,
            "hour":         hour,
            "day":          day,
            "day_name":     day_names[day],
            "month":        month,
            **prediction,
        })


# ─── LSTM Occupancy Forecast ───────────────────────────────────────────────────

class LSTMForecastView(APIView):
    """
    GET /api/ai/lstm-forecast/?lot_id=<id>

    Returns predicted occupancy % for the next 4 hours using the trained LSTM.
    Uses recent booking history for the lot, or falls back to synthetic patterns.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        import pandas as pd
        from django.utils import timezone as tz
        from parking.models import ParkingLot
        from ai_engine.ml_models.lstm_model import OccupancyForecaster, _generate_synthetic_hourly

        lot_id = request.query_params.get("lot_id")

        if not OccupancyForecaster.is_trained():
            return Response({
                "error": "LSTM model not trained yet.",
                "hint": "Run: python manage.py train_lstm",
            }, status=503)

        try:
            lot = ParkingLot.objects.get(id=lot_id, is_active=True) if lot_id else None
        except ParkingLot.DoesNotExist:
            return Response({"error": "Parking lot not found."}, status=404)

        forecaster = OccupancyForecaster.load()

        # Build recent 24-hour context from bookings or synthetic fallback
        now          = tz.now()
        recent_hours = _build_recent_context(lot, now)
        predictions  = forecaster.forecast(recent_hours)

        hours_ahead = []
        for i, occ in enumerate(predictions, start=1):
            future_hour = (now.hour + i) % 24
            hours_ahead.append({
                "hour":        future_hour,
                "hour_label":  f"{future_hour:02d}:00",
                "occupancy":   round(occ, 3),
                "occupancy_pct": round(occ * 100, 1),
                "label": (
                    "Very Busy"  if occ > 0.8 else
                    "Busy"       if occ > 0.6 else
                    "Moderate"   if occ > 0.4 else
                    "Quiet"
                ),
            })

        return Response({
            "lot_id":       lot_id,
            "lot_name":     lot.name if lot else "All Lots",
            "forecast_from": now.strftime("%H:%M"),
            "next_4_hours": hours_ahead,
            "model":        "LSTM",
        })


def _build_recent_context(lot, now):
    """
    Build a 24-row DataFrame representing the last 24 hours of occupancy
    for the given lot. Falls back to synthetic if not enough booking data.
    """
    import pandas as pd
    import numpy as np
    from bookings.models import Booking
    from ai_engine.ml_models.lstm_model import _generate_synthetic_hourly

    rows = []
    for offset in range(24, 0, -1):
        target_hour = (now.hour - offset) % 24
        day_of_week = now.weekday()
        is_weekend  = float(day_of_week >= 5)

        if lot:
            total = Booking.objects.filter(
                slot__zone__floor__lot=lot,
                start_time__hour=target_hour,
                status__in=["confirmed", "active", "completed"],
            ).count()
        else:
            total = Booking.objects.filter(
                start_time__hour=target_hour,
                status__in=["confirmed", "active", "completed"],
            ).count()

        # Rough estimate: if >5 bookings at that hour, treat as high occupancy
        occupancy = min(total / 20.0, 1.0) if total > 0 else _synthetic_occ(target_hour, day_of_week)

        rows.append({
            "hour":           target_hour,
            "day_of_week":    day_of_week,
            "is_weekend":     is_weekend,
            "occupancy_rate": occupancy,
        })

    return pd.DataFrame(rows)


def _synthetic_occ(hour, day_of_week):
    import numpy as np
    is_weekend = day_of_week >= 5
    if is_weekend:
        return float(np.clip(0.15 + 0.3 * np.exp(-((hour - 12) ** 2) / 18), 0, 1))
    morning = 0.4  * np.exp(-((hour - 9)  ** 2) / 4)
    lunch   = 0.35 * np.exp(-((hour - 13) ** 2) / 3)
    evening = 0.5  * np.exp(-((hour - 18) ** 2) / 5)
    return float(np.clip(0.05 + morning + lunch + evening, 0, 1))


# ─── Dataset & Model Status ────────────────────────────────────────────────────

class DatasetStatusView(APIView):
    """
    GET /api/ai/dataset-status/

    Returns availability status of all 12 datasets and all 3 model checkpoints.
    Useful for the admin dashboard to know what's been downloaded/trained.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        import os
        from ai_engine.datasets.registry import get_all_datasets

        datasets = []
        for i, ds in enumerate(get_all_datasets(), start=1):
            info = ds.info()
            datasets.append({
                "index":     i,
                "name":      info.get("name"),
                "type":      info.get("type"),
                "source":    info.get("source"),
                "size":      info.get("size"),
                "available": ds.is_available(),
                "url":       info.get("url", ""),
                "notes":     info.get("notes", ""),
            })

        checkpoints = {
            "cnn":            "ai_engine/checkpoints/cnn_best.pth",
            "random_forest":  "ai_engine/checkpoints/random_forest.pkl",
            "lstm":           "ai_engine/checkpoints/lstm_model.pth",
        }
        models = {}
        for key, path in checkpoints.items():
            exists = os.path.exists(path)
            models[key] = {
                "trained":   exists,
                "path":      path,
                "size_kb":   round(os.path.getsize(path) / 1024, 1) if exists else None,
            }

        return Response({
            "datasets":        datasets,
            "models":          models,
            "datasets_ready":  sum(1 for d in datasets if d["available"]),
            "datasets_total":  len(datasets),
            "models_trained":  sum(1 for m in models.values() if m["trained"]),
        })
