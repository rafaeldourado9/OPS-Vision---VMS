import uuid
from django.db import models


class Tenant(models.Model):
    """Instância de cidade/cliente"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reseller = models.ForeignKey('resellers.Reseller', on_delete=models.CASCADE, related_name='tenants')
    license = models.ForeignKey('franchise.License', on_delete=models.PROTECT, related_name='tenants')
    name = models.CharField(max_length=255)
    subdomain = models.CharField(max_length=63, unique=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenants'
        indexes = [
            models.Index(fields=['subdomain']),
            models.Index(fields=['reseller', 'active']),
        ]

    def __str__(self):
        return self.name
