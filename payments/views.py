from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from .models import Payment, Transaction, Invoice, Subscription, Review, Rating
from .serializers import (
    PaymentSerializer, TransactionSerializer, InvoiceSerializer,
    SubscriptionSerializer, ReviewSerializer, RatingSerializer,
)
from .services import confirm_payment, process_refund, get_payment_summary


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "method"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Payment.objects.select_related(
                "booking__slot", "user"
            ).prefetch_related("transactions").all()
        return Payment.objects.filter(user=self.request.user).select_related(
            "booking__slot"
        ).prefetch_related("transactions")

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        """
        POST /api/payments/{id}/confirm/
        Simulates a payment gateway callback — marks payment successful,
        records debit transaction, generates invoice.
        Body: { "method": "upi" }  (optional, updates payment method)
        """
        payment = self.get_object()
        method = request.data.get("method")
        if method:
            payment.method = method
            payment.save(update_fields=["method"])
        try:
            payment, invoice = confirm_payment(payment)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": "Payment confirmed.",
            "payment": PaymentSerializer(payment).data,
            "invoice_number": invoice.invoice_number,
            "invoice_id": str(invoice.id),
        })

    @action(detail=True, methods=["post"], url_path="refund")
    def refund(self, request, pk=None):
        """
        POST /api/payments/{id}/refund/
        Applies refund policy automatically based on how far away the booking is.
        Body: { "amount": 150.00 }  (optional — override refund amount)
        """
        payment = self.get_object()
        requested_amount = request.data.get("amount")
        try:
            payment = process_refund(payment, requested_amount=requested_amount)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": "Refund processed.",
            "refund_amount": str(payment.refund_amount),
            "payment": PaymentSerializer(payment).data,
        })

    @action(detail=True, methods=["get"], url_path="invoice")
    def invoice(self, request, pk=None):
        """GET /api/payments/{id}/invoice/ — retrieve invoice for a payment."""
        payment = self.get_object()
        try:
            invoice = payment.invoice
        except Invoice.DoesNotExist:
            return Response(
                {"error": "Invoice not yet generated. Complete payment first."},
                status=404,
            )
        return Response(InvoiceSerializer(invoice).data)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """GET /api/payments/summary/ — personal payment stats."""
        user = None if request.user.is_staff else request.user
        return Response(get_payment_summary(user=user))


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only invoice access — users see their own, admins see all."""
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    ordering = ["-issued_at"]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Invoice.objects.select_related("payment__user").all()
        return Invoice.objects.filter(payment__user=self.request.user)


class SubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Subscription.objects.select_related("user", "lot").all()
        return Subscription.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        """GET /api/payments/subscriptions/active/ — current active subscription."""
        from django.utils import timezone
        sub = self.get_queryset().filter(
            status="active", expires_at__gte=timezone.now()
        ).first()
        if not sub:
            return Response({"detail": "No active subscription."}, status=404)
        return Response(SubscriptionSerializer(sub).data)


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        lot_id = self.request.query_params.get("lot")
        qs = Review.objects.filter(is_approved=True).select_related("user", "lot")
        if lot_id:
            qs = qs.filter(lot_id=lot_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RatingViewSet(viewsets.ModelViewSet):
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        lot_id = self.request.query_params.get("lot")
        qs = Rating.objects.select_related("user", "lot").all()
        if lot_id:
            qs = qs.filter(lot_id=lot_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="lot-average")
    def lot_average(self, request):
        """GET /api/payments/ratings/lot-average/?lot={id} — avg rating for a lot."""
        lot_id = request.query_params.get("lot")
        if not lot_id:
            return Response({"error": "lot query param required."}, status=400)
        from django.db.models import Avg, Count
        stats = Rating.objects.filter(lot_id=lot_id).aggregate(
            average=Avg("score"), count=Count("id")
        )
        return Response({
            "lot_id": lot_id,
            "average_rating": round(stats["average"] or 0, 1),
            "total_ratings": stats["count"],
        })


class AdminRevenueView(APIView):
    """GET /api/payments/admin/revenue/ — full revenue stats for admin dashboard."""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        from django.db.models import Sum, Count
        from django.db.models.functions import TruncDate
        from .models import Payment

        daily = (
            Payment.objects.filter(status="success")
            .annotate(date=TruncDate("paid_at"))
            .values("date")
            .annotate(revenue=Sum("amount"), count=Count("id"))
            .order_by("-date")[:30]
        )

        return Response({
            "summary": get_payment_summary(),
            "daily_revenue": [
                {"date": str(d["date"]), "revenue": float(d["revenue"]), "transactions": d["count"]}
                for d in daily
            ],
        })
