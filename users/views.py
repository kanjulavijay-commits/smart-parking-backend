from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from .models import User, Role, Permission, AuditLog, SupportTicket
from .serializers import (
    UserSerializer, RegisterSerializer, ChangePasswordSerializer,
    RoleSerializer, PermissionSerializer, AuditLogSerializer, SupportTicketSerializer,
    CustomTokenObtainPairSerializer, VerifyEmailSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer,
)
from .emails import send_verification_email, send_password_reset_email


class CustomTokenObtainPairView(TokenObtainPairView):
    """POST /api/auth/login/ — returns access + refresh tokens plus user profile."""
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        # Update last_login_at on successful login
        if response.status_code == 200:
            try:
                user = User.objects.get(email=request.data.get("email"))
                user.last_login_at = timezone.now()
                user.save(update_fields=["last_login_at"])
            except User.DoesNotExist:
                pass
        return response


class LogoutView(APIView):
    """POST /api/auth/logout/ — blacklists the refresh token so it can never be reused."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully."})
        except Exception:
            return Response({"error": "Invalid or missing refresh token."}, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(generics.CreateAPIView):
    """POST /api/users/register/ — creates account and sends verification email."""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        try:
            send_verification_email(user)
        except Exception:
            # Don't fail registration if email service is down
            pass

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        response.data = {
            "message": "Account created. Check your email to verify your address.",
            "email": response.data.get("email"),
        }
        return response


class VerifyEmailView(APIView):
    """POST /api/auth/verify-email/ — marks the user's email as verified."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.is_email_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=["is_email_verified", "email_verified_at"])
        return Response({"message": "Email verified successfully. You can now log in."})


class ResendVerificationView(APIView):
    """POST /api/auth/resend-verification/ — resends verification email."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        try:
            user = User.objects.get(email=email)
            if user.is_email_verified:
                return Response({"message": "Email is already verified."})
            send_verification_email(user)
            return Response({"message": "Verification email resent."})
        except User.DoesNotExist:
            # Don't reveal whether the email exists
            return Response({"message": "If that email exists, a verification link was sent."})


class ForgotPasswordView(APIView):
    """POST /api/auth/forgot-password/ — sends a password reset email."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = User.objects.get(email=serializer.validated_data["email"])
            send_password_reset_email(user)
        except User.DoesNotExist:
            pass
        # Always return the same message — never confirm if an email exists
        return Response({"message": "If that email is registered, a reset link has been sent."})


class ResetPasswordView(APIView):
    """POST /api/auth/reset-password/ — sets a new password using the reset token."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response({"message": "Password has been reset. You can now log in."})


class UserViewSet(viewsets.ModelViewSet):
    """CRUD for users — admins see all, regular users only see themselves."""
    serializer_class = UserSerializer
    queryset = User.objects.select_related("role").all()

    def get_permissions(self):
        if self.action in ["list", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if self.request.user.is_staff:
            return User.objects.select_related("role").all()
        return User.objects.filter(id=self.request.user.id)

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """GET /api/users/me/ — current user's profile."""
        return Response(UserSerializer(request.user).data)

    @action(detail=False, methods=["patch"], url_path="me/update")
    def update_me(self, request):
        """PATCH /api/users/me/update/ — update own profile."""
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        """POST /api/users/change-password/ — change password while logged in."""
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response({"error": "Old password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response({"message": "Password updated successfully."})


class RoleViewSet(viewsets.ModelViewSet):
    serializer_class = RoleSerializer
    queryset = Role.objects.prefetch_related("permissions").all()
    permission_classes = [permissions.IsAdminUser]


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PermissionSerializer
    queryset = Permission.objects.all()
    permission_classes = [permissions.IsAdminUser]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("user").all()
    permission_classes = [permissions.IsAdminUser]


class SupportTicketViewSet(viewsets.ModelViewSet):
    serializer_class = SupportTicketSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return SupportTicket.objects.select_related("user", "assigned_to").all()
        return SupportTicket.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
