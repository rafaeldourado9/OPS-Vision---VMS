"""Admin para agents."""
from django.contrib import admin

from .models import Agent


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    """Admin para Agent."""

    list_display = ["name", "tenant", "status", "last_heartbeat", "version"]
    list_filter = ["status", "tenant"]
    search_fields = ["name"]
    readonly_fields = ["api_key", "created_at", "updated_at"]
