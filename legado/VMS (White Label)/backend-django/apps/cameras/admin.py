from django.contrib import admin
from .models import Camera, DetectionMask


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'stream_protocol', 'ia_enabled', 'ia_status', 'online', 'created_at']
    list_filter = ['stream_protocol', 'ia_enabled', 'ia_status', 'online', 'tenant']
    search_fields = ['name', 'address']
    readonly_fields = ['id', 'stream_key', 'created_at']


@admin.register(DetectionMask)
class DetectionMaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'camera', 'tenant', 'active', 'created_at']
    list_filter = ['active', 'tenant']
