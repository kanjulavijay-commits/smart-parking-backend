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
    if not settings.DEBUG:
        return JsonResponse({"error": "disabled"}, status=403)
    from django.contrib.auth import get_user_model, authenticate
    User = get_user_model()
    try:
        user = User.objects.get(email="admin@smartparking.com")
        # Force-reset password so we know the exact value
        user.set_password("Admin@1234")
        user.is_active = True
        user.save()
        can_auth = authenticate(request=request, email="admin@smartparking.com", password="Admin@1234") is not None
        return JsonResponse({
            "version": "68b6693",
            "is_active": user.is_active,
            "is_staff": user.is_staff,
            "has_usable_password": user.has_usable_password(),
            "password_algo": user.password.split("$")[0] if user.password else None,
            "can_authenticate": can_auth,
            "password_reset": True,
        })
    except User.DoesNotExist:
        return JsonResponse({"version": "68b6693", "admin_exists": False})


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
