from rest_framework import serializers
from .models import AIRecommendation


class AIRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIRecommendation
        fields = [
            "id", "user", "recommendation_type", "recommended_slot", "recommended_lot",
            "confidence", "reasoning", "context_data", "was_accepted", "created_at",
        ]
        read_only_fields = ["id", "user", "created_at"]
