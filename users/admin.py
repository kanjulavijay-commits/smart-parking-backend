from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role, Permission, AuditLog, SupportTicket


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "full_name", "role", "is_active", "is_email_verified", "created_at"]
    list_filter = ["is_active", "is_staff", "is_email_verified", "role"]
    search_fields = ["email", "full_name", "phone"]
    ordering = ["-created_at"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal", {"fields": ("full_name", "phone", "profile_picture")}),
        ("Role & Status", {"fields": ("role", "is_active", "is_staff", "is_superuser", "is_email_verified")}),
        ("Timestamps", {"fields": ("created_at", "updated_at", "last_login_at")}),
    )
    readonly_fields = ["created_at", "updated_at", "last_login_at"]
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "password1", "password2"),
        }),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "created_at"]
    filter_horizontal = ["permissions"]


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ["name", "codename"]
    search_fields = ["name", "codename"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["user", "action", "model_name", "object_id", "ip_address", "created_at"]
    list_filter = ["model_name", "action"]
    search_fields = ["user__email", "action", "model_name"]
    readonly_fields = ["user", "action", "model_name", "object_id", "changes", "ip_address", "created_at"]


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ["subject", "user", "status", "priority", "created_at"]
    list_filter = ["status", "priority"]
    search_fields = ["subject", "user__email"]
