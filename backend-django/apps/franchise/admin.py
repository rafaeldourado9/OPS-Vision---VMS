from django.contrib import admin
from .models import License


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ['reseller', 'max_cameras', 'valid_until', 'active', 'created_at']
    list_filter = ['active', 'reseller']
    search_fields = ['reseller__name']
