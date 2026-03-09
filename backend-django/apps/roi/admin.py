from django.contrib import admin
from .models import RegionOfInterest


@admin.register(RegionOfInterest)
class RegionOfInterestAdmin(admin.ModelAdmin):
    list_display = ['name', 'camera', 'ia_type', 'active', 'created_at']
    list_filter = ['ia_type', 'active', 'camera__tenant']
    search_fields = ['name', 'camera__name']
    readonly_fields = ['id', 'created_at']
