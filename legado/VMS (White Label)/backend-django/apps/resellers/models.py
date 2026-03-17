import uuid
from django.db import models


class Reseller(models.Model):
    """Revendedor/Franqueado - White Label"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    custom_domain = models.CharField(max_length=255, unique=True, null=True, blank=True)
    primary_color = models.CharField(max_length=7, default='#1E40AF')
    secondary_color = models.CharField(max_length=7, default='#3B82F6')
    logo_url = models.URLField(null=True, blank=True)
    favicon_url = models.URLField(null=True, blank=True)
    dark_mode_default = models.BooleanField(default=False)
    terms_url = models.URLField(null=True, blank=True)
    privacy_url = models.URLField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'resellers'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['custom_domain']),
        ]

    def __str__(self):
        return self.name
