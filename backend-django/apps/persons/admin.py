from django.contrib import admin
from .models import KnownPerson, PersonPhoto


class PersonPhotoInline(admin.TabularInline):
    model = PersonPhoto
    extra = 1


@admin.register(KnownPerson)
class KnownPersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'active', 'created_at']
    list_filter = ['active', 'tenant']
    search_fields = ['name']
    inlines = [PersonPhotoInline]
