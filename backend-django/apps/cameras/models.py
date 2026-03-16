import uuid
from django.db import models


class Camera(models.Model):
    """Câmera de monitoramento"""
    
    PROTOCOL_CHOICES = [
        ('rtsp', 'RTSP'),
        ('rtmp', 'RTMP'),
    ]
    
    RETENTION_CHOICES = [
        (7, '7 dias'),
        (15, '15 dias'),
        (30, '30 dias'),
    ]
    
    IA_STATUS_CHOICES = [
        ('disabled', 'Desabilitado'),
        ('ia_pending', 'Aguardando Configuração'),
        ('active', 'Ativo'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='cameras')
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    stream_protocol = models.CharField(max_length=10, choices=PROTOCOL_CHOICES)
    stream_url = models.CharField(max_length=500, null=True, blank=True)
    stream_key = models.UUIDField(null=True, blank=True, editable=False)
    retention_days = models.IntegerField(choices=RETENTION_CHOICES, default=7)
    ia_enabled = models.BooleanField(default=False)
    ia_status = models.CharField(max_length=20, choices=IA_STATUS_CHOICES, default='disabled')
    online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cameras'
        indexes = [
            models.Index(fields=['tenant', 'online']),
            models.Index(fields=['tenant', 'ia_enabled']),
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"

    def save(self, *args, **kwargs):
        # Gera stream_key para RTMP
        if self.stream_protocol == 'rtmp' and not self.stream_key:
            self.stream_key = uuid.uuid4()

        # Atualiza ia_status baseado em ia_enabled
        if self.ia_enabled and self.ia_status == 'disabled':
            self.ia_status = 'ia_pending'
        elif not self.ia_enabled:
            self.ia_status = 'disabled'

        super().save(*args, **kwargs)


class DetectionMask(models.Model):
    """Máscara de detecção para ignorar áreas da imagem."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='detection_masks')
    camera = models.ForeignKey('cameras.Camera', on_delete=models.CASCADE, related_name='detection_masks')
    polygon = models.JSONField(help_text='Lista de pontos [[x, y], ...]')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'detection_masks'
        indexes = [
            models.Index(fields=['tenant', 'camera']),
            models.Index(fields=['camera', 'active']),
        ]

    def __str__(self):
        return f"DetectionMask {self.id} ({self.camera.name})"
