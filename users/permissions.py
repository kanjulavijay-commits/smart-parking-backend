"""
users/permissions.py — Role-Based Access Control (RBAC) permission classes.

How RBAC works here:
  Every User has a Role (Admin / Operator / Driver).
  Each Role has many Permissions (codenames like 'can_manage_lots').
  These DRF permission classes check both the role name and codenames.
"""

from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Only users with the 'admin' role."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role is not None
            and request.user.role.name == "admin"
        )


class IsOperator(BasePermission):
    """Only users with the 'operator' role."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role is not None
            and request.user.role.name == "operator"
        )


class IsDriver(BasePermission):
    """Only users with the 'driver' role."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role is not None
            and request.user.role.name == "driver"
        )


class IsAdminOrOperator(BasePermission):
    """Admin or Operator can access."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role is not None
            and request.user.role.name in ("admin", "operator")
        )


class HasRolePermission(BasePermission):
    """
    Checks if the user's role has a specific permission codename.

    Usage in a view:
        permission_classes = [HasRolePermission]
        required_permission = "can_manage_lots"
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        required = getattr(view, "required_permission", None)
        if not required:
            return True
        if not request.user.role:
            return False
        return request.user.role.permissions.filter(codename=required).exists()


class IsOwnerOrAdmin(BasePermission):
    """Object-level: only the owner or an admin can access."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "owner", None)
        return owner == request.user
