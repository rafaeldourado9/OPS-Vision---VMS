from django.contrib import admin
from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'subdomain', 'reseller', 'active', 'created_at']
    list_filter = ['active', 'reseller']
    search_fields = ['name', 'subdomain']
