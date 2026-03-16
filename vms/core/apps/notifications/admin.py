"""Painel admin para notificações."""
from django.contrib import admin

from .models import NotificationLog, NotificationRule


@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    """Admin para NotificationRule."""

    list_display = (
        "name",
        "tenant",
        "event_type_pattern",
        "channel",
        "is_active",
        "created_at",
    )
    list_filter = ("tenant", "is_active", "channel")
    search_fields = ("name", "event_type_pattern", "destination")


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """Admin para NotificationLog."""

    list_display = (
        "id",
        "rule",
        "event_type",
        "status",
        "response_code",
        "created_at",
    )
    list_filter = ("status", "response_code", "created_at")
    search_fields = ("event_type", "response_body")
    readonly_fields = (
        "rule",
        "event_id",
        "event_type",
        "status",
        "response_code",
        "response_body",
        "created_at",
    )

    def has_add_permission(self, request):
        """Logs não podem ser criados manualmente."""
        return False
