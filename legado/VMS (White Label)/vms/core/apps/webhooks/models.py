"""Models para webhooks."""
from django.db import models


class WebhookLog(models.Model):
    """Log de webhooks recebidos para auditoria."""

    class Source(models.TextChoices):
        ALPR = "alpr", "ALPR"
        MEDIAMTX = "mediamtx", "MediaMTX"
        ONVIF = "onvif", "ONVIF"
        OTHER = "other", "Outro"

    source: str = models.CharField(
        max_length=20,
        choices=Source.choices,
    )
    endpoint: str = models.CharField(max_length=255)
    payload = models.JSONField(default=dict)
    status_code: int = models.IntegerField(default=200)
    processed: bool = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.source} → {self.endpoint} @ {self.created_at:%H:%M:%S}"
