from django.contrib import admin
from .models import Segment, Clip, StoragePolicy, StorageFile


@admin.register(Segment)
class SegmentAdmin(admin.ModelAdmin):
    list_display = ['camera', 'start_time', 'end_time', 'file_size', 'tier_order', 'expires_at']
    list_filter = ['camera__tenant', 'tier_order', 'expires_at']
    search_fields = ['camera__name']
    readonly_fields = ['id', 'created_at']


@admin.register(Clip)
class ClipAdmin(admin.ModelAdmin):
    list_display = ['name', 'camera', 'status', 'file_size', 'created_at']
    list_filter = ['status', 'camera__tenant']
    search_fields = ['name', 'camera__name']
    readonly_fields = ['id', 'created_at']


@admin.register(StoragePolicy)
class StoragePolicyAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'category', 'tier_order', 'path', 'max_age_hours', 'max_size_gb', 'enabled']
    list_filter = ['category', 'tier_order', 'enabled', 'tenant']
    list_editable = ['max_age_hours', 'max_size_gb', 'enabled']
    ordering = ['tenant', 'category', 'tier_order']


@admin.register(StorageFile)
class StorageFileAdmin(admin.ModelAdmin):
    list_display = ['category', 'subcategory', 'camera', 'file_size', 'tier_order', 'created_at']
    list_filter = ['category', 'subcategory', 'tier_order']
    search_fields = ['file_path', 'camera__name']
    readonly_fields = ['id', 'created_at']
