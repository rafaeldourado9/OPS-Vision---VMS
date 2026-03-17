import uuid
from django.db import models


class AIEvent(models.Model):
    """Evento detectado pela IA"""
    
    EVENT_TYPE_CHOICES = [
        # Sprint 1
        ('lpr', 'Reconhecimento de Placa'),
        ('crowd', 'Aglomeração'),
        ('intrusion', 'Intrusão'),
        ('object_detected', 'Objeto Detectado'),
        # Sprint 2 (tracking)
        ('vehicle_traffic', 'Tráfego de Veículos'),
        ('human_traffic', 'Tráfego Humano'),
        ('line_crossing', 'Cruzamento de Linha'),
        ('loitering', 'Perambulação'),
        ('abandoned_object', 'Objeto Abandonado'),
        ('queue_alert', 'Alerta de Fila'),
        # Sprint 3
        ('facial_match', 'Reconhecimento Facial - Match'),
        ('facial_unknown', 'Pessoa Desconhecida'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='ai_events')
    camera = models.ForeignKey('cameras.Camera', on_delete=models.CASCADE, related_name='ai_events')
    roi = models.ForeignKey('roi.RegionOfInterest', on_delete=models.SET_NULL, null=True, related_name='ai_events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    snapshot_path = models.CharField(max_length=500)
    event_data = models.JSONField()  # {plate, confidence} para LPR
    detected_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_events'
        indexes = [
            models.Index(fields=['tenant', 'detected_at']),
            models.Index(fields=['camera', 'event_type']),
            models.Index(fields=['detected_at']),
        ]
        ordering = ['-detected_at']

    def __str__(self):
        return f"{self.event_type} - {self.camera.name} - {self.detected_at}"
