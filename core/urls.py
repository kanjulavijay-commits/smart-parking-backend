from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView
from users.views import (
    CustomTokenObtainPairView, LogoutView,
    VerifyEmailView, ResendVerificationView,
    ForgotPasswordView, ResetPasswordView,
)

urlpatterns = [
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
