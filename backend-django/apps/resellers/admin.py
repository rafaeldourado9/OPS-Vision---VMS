from django.contrib import admin
from .models import Reseller


@admin.register(Reseller)
class ResellerAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'custom_domain', 'active', 'created_at']
    list_filter = ['active']
    search_fields = ['name', 'slug', 'custom_domain']
    prepopulated_fields = {'slug': ('name',)}
