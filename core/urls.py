from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenRefreshView
from users.views import (
    CustomTokenObtainPairView, LogoutView,
    VerifyEmailView, ResendVerificationView,
    ForgotPasswordView, ResetPasswordView,
)

def health(request):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    admin_exists = User.objects.filter(email="admin@smartparking.com").exists()
    admin_active = User.objects.filter(email="admin@smartparking.com", is_active=True).exists()
    return JsonResponse({"version": "98b11d0", "admin_exists": admin_exists, "admin_active": admin_active})


urlpatterns = [
    path("health/", health),
    path("admin/", admin.site.urls),

    # ── Auth ──────────────────────────────────────────────────
    path("api/auth/login/",               CustomTokenObtainPairView.as_view(), name="login"),
    path("api/auth/refresh/",             TokenRefreshView.as_view(),          name="token_refresh"),
    path("api/auth/logout/",              LogoutView.as_view(),                name="logout"),
    path("api/auth/verify-email/",        VerifyEmailView.as_view(),           name="verify_email"),
    path("api/auth/resend-verification/", ResendVerificationView.as_view(),    name="resend_verification"),
    path("api/auth/forgot-password/",     ForgotPasswordView.as_view(),        name="forgot_password"),
    path("api/auth/reset-password/",      ResetPasswordView.as_view(),         name="reset_password"),

    # ── App routers ───────────────────────────────────────────
    path("api/users/",         include("users.urls")),
    path("api/parking/",       include("parking.urls")),
    path("api/bookings/",      include("bookings.urls")),
    path("api/payments/",      include("payments.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/ai/",            include("ai_engine.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
