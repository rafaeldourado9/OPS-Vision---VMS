from django.contrib import admin
from .models import Segment


@admin.register(Segment)
class SegmentAdmin(admin.ModelAdmin):
    list_display = ['camera', 'start_time', 'end_time', 'file_size', 'expires_at']
    list_filter = ['camera__tenant', 'expires_at']
    search_fields = ['camera__name']
    readonly_fields = ['id', 'created_at']
