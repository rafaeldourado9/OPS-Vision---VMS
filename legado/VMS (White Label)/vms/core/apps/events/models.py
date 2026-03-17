"""Models para eventos do sistema."""
from django.db import models


class Event(models.Model):
    """Evento gerado por câmera, analytics ou sistema."""

    class EventType(models.TextChoices):
        CAMERA_ONLINE = "camera.online", "Câmera Online"
        CAMERA_OFFLINE = "camera.offline", "Câmera Offline"
        MOTION_DETECTED = "motion.detected", "Movimento Detectado"
        ALPR_DETECTED = "alpr.detected", "Placa Detectada"
        INTRUSION_DETECTED = "intrusion.detected", "Intrusão Detectada"
        FIRE_DETECTED = "fire.detected", "Incêndio Detectado"
        VIDEO_LOSS = "video.loss", "Perda de Vídeo"
        TAMPERING_DETECTED = "tampering.detected", "Tamper Detectado"
        LINE_CROSSING = "line_crossing.detected", "Cruzamento de Linha"
        FACE_DETECTED = "face.detected", "Face Detectada"

    event_type: str = models.CharField(
        max_length=50,
        choices=EventType.choices,
    )
    payload = models.JSONField(default=dict)
    camera = models.ForeignKey(
        "cameras.Camera",
        on_delete=models.CASCADE,
        related_name="events",
        null=True,
        blank=True,
    )
    tenant = models.ForeignKey(
        "users.Tenant",
        on_delete=models.CASCADE,
        related_name="events",
    )
    payload = models.JSONField(
        help_text="Dados específicos do evento em formato JSON",
        default=dict,
        blank=True,
    )
    plate = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        db_index=True,
        help_text="Placa do veículo (para eventos ALPR)",
    )
    confidence = models.FloatField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Nível de confiança da detecção (para eventos ALPR)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "events_event"
        ordering = ["-created_at"]
        verbose_name = "Evento"
        verbose_name_plural = "Eventos"
        indexes = [
            models.Index(fields=["event_type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["tenant", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M}"
