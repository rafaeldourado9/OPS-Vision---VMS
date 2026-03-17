import uuid
from django.db import models


class License(models.Model):
    """Licença de uso por revendedor"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reseller = models.ForeignKey('resellers.Reseller', on_delete=models.CASCADE, related_name='licenses')
    max_cameras = models.IntegerField(default=10)
    valid_until = models.DateField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'licenses'
        indexes = [
            models.Index(fields=['reseller', 'active']),
        ]

    def __str__(self):
        return f"{self.reseller.name} - {self.max_cameras} câmeras"
