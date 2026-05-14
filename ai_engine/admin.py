from django.contrib import admin
from .models import AIRecommendation


@admin.register(AIRecommendation)
class AIRecommendationAdmin(admin.ModelAdmin):
    list_display = ["user", "recommendation_type", "confidence", "was_accepted", "created_at"]
    list_filter = ["recommendation_type", "was_accepted"]
    search_fields = ["user__email"]
