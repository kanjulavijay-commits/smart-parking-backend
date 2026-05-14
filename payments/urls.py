from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PaymentViewSet, InvoiceViewSet, SubscriptionViewSet,
    ReviewViewSet, RatingViewSet, AdminRevenueView,
)

router = DefaultRouter()
router.register("", PaymentViewSet, basename="payments")
router.register("invoices", InvoiceViewSet, basename="invoices")
router.register("subscriptions", SubscriptionViewSet, basename="subscriptions")
router.register("reviews", ReviewViewSet, basename="reviews")
router.register("ratings", RatingViewSet, basename="ratings")

urlpatterns = [
    path("admin/revenue/", AdminRevenueView.as_view(), name="admin-revenue"),
    path("", include(router.urls)),
]
