from django.contrib import admin
from .models import Payment, Transaction, Invoice, Subscription, Review, Rating


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "amount", "method", "status", "paid_at", "created_at"]
    list_filter = ["status", "method"]
    search_fields = ["user__email"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["payment", "amount", "transaction_type", "created_at"]
    list_filter = ["transaction_type"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "payment", "total", "issued_at"]
    search_fields = ["invoice_number"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "lot", "plan_type", "status", "expires_at"]
    list_filter = ["status", "plan_type"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["user", "lot", "title", "is_approved", "created_at"]
    list_filter = ["is_approved"]
    actions = ["approve_reviews"]

    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
    approve_reviews.short_description = "Approve selected reviews"


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["user", "lot", "score", "created_at"]
    list_filter = ["score"]
