import uuid
from django.db import models


class RegionOfInterest(models.Model):
    """Região de interesse para análise de IA"""
    
    IA_TYPE_CHOICES = [
        ('lpr', 'Reconhecimento de Placas'),
        ('intrusion', 'Detecção de Intrusão'),
        ('crowd', 'Detecção de Aglomeração'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='rois')
    camera = models.ForeignKey('cameras.Camera', on_delete=models.CASCADE, related_name='rois')
    name = models.CharField(max_length=255)
    polygon = models.JSONField()  # Lista de [x, y] normalizado 0-1
    ia_type = models.CharField(max_length=20, choices=IA_TYPE_CHOICES)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'regions_of_interest'
        indexes = [
            models.Index(fields=['tenant', 'camera']),
            models.Index(fields=['camera', 'active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.camera.name})"
