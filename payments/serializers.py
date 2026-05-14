from rest_framework import serializers
from .models import Payment, Transaction, Invoice, Subscription, Review, Rating


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["id", "payment", "amount", "transaction_type", "reference_id", "description", "created_at"]
        read_only_fields = ["id", "created_at"]


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ["id", "payment", "invoice_number", "subtotal", "tax", "total", "pdf_file", "issued_at"]
        read_only_fields = ["id", "invoice_number", "issued_at"]


class PaymentSerializer(serializers.ModelSerializer):
    transactions = TransactionSerializer(many=True, read_only=True)
    invoice = InvoiceSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "booking", "user", "amount", "method", "status",
            "gateway_reference", "paid_at", "refunded_at", "refund_amount",
            "transactions", "invoice", "created_at",
        ]
        read_only_fields = ["id", "user", "status", "paid_at", "refunded_at", "created_at"]


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = [
            "id", "user", "lot", "plan_type", "status",
            "price", "starts_at", "expires_at", "auto_renew", "created_at",
        ]
        read_only_fields = ["id", "user", "status", "created_at"]


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["id", "user", "lot", "title", "body", "is_approved", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "is_approved", "created_at", "updated_at"]


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ["id", "user", "lot", "score", "created_at"]
        read_only_fields = ["id", "user", "created_at"]

    def validate_score(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Score must be between 1 and 5.")
        return value
