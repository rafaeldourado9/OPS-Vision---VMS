from django.contrib import admin
from .models import AIEvent


@admin.register(AIEvent)
class AIEventAdmin(admin.ModelAdmin):
    list_display = ['camera', 'event_type', 'detected_at', 'created_at']
    list_filter = ['event_type', 'camera__tenant', 'detected_at']
    search_fields = ['camera__name', 'event_data']
    readonly_fields = ['id', 'created_at']
