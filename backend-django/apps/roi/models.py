import uuid
from django.db import models


class RegionOfInterest(models.Model):
    """Região de interesse para análise de IA"""
    
    IA_TYPE_CHOICES = [
        # Sprint 1
        ('lpr', 'Reconhecimento de Placas'),
        ('crowd', 'Detecção de Multidões'),
        ('intrusion', 'Intrusão'),
        ('object_detection', 'Detecção de Objetos'),
        # Sprint 2 (tracking)
        ('vehicle_traffic', 'Tráfego de Veículos'),
        ('human_traffic', 'Tráfego Humano'),
        ('line_crossing', 'Cruzamento de Linha'),
        ('loitering', 'Perambulação'),
        ('abandoned_object', 'Objeto Abandonado'),
        ('queue', 'Detecção de Fila'),
        # Sprint 3
        ('facial', 'Reconhecimento Facial'),
        # Sprint 4
        ('heatmap', 'Mapa de Calor'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='rois')
    camera = models.ForeignKey('cameras.Camera', on_delete=models.CASCADE, related_name='rois')
    name = models.CharField(max_length=255)
    polygon = models.JSONField()  # Lista de [x, y] normalizado 0-1
    ia_type = models.CharField(max_length=20, choices=IA_TYPE_CHOICES)
    config = models.JSONField(default=dict, blank=True)
    # Exemplos de config por tipo:
    # crowd/queue: {"threshold": 10}
    # loitering:   {"max_seconds": 30}
    # line_crossing: {"line": [[x1,y1],[x2,y2]], "direction": "both"}
    # object_detection/intrusion: {"classes": ["person","car"]}
    # Multi-analytic mode: one line ROI → multiple analytics.
    # When set, ia_type is ignored. Values are keys from IA_TYPE_CHOICES.
    ia_types = models.JSONField(default=list, blank=True)

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
