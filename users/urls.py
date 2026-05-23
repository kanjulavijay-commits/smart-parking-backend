from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, UserViewSet, RoleViewSet, PermissionViewSet,
    AuditLogViewSet, SupportTicketViewSet,
)

router = DefaultRouter()
router.register("roles", RoleViewSet, basename="roles")
router.register("permissions", PermissionViewSet, basename="permissions")
router.register("audit-logs", AuditLogViewSet, basename="audit-logs")
router.register("support", SupportTicketViewSet, basename="support")
router.register("", UserViewSet, basename="users")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("", include(router.urls)),
]
