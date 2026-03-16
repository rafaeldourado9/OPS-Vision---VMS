"""Models para câmeras."""
from django.db import models


class Camera(models.Model):
    """Representa uma câmera de vigilância no sistema."""

    class RetentionDays(models.IntegerChoices):
        SEVEN = 7, "7 dias"
        FIFTEEN = 15, "15 dias"
        THIRTY = 30, "30 dias"

    class Manufacturer(models.TextChoices):
        HIKVISION = "hikvision", "Hikvision"
        INTELBRAS = "intelbras", "Intelbras"
        DAHUA = "dahua", "Dahua"
        OTHER = "other", "Outro"

    name: str = models.CharField(max_length=255)
    location: str = models.CharField(max_length=255)
    rtsp_url: str = models.URLField(blank=True)
    manufacturer: str = models.CharField(
        max_length=20,
        choices=Manufacturer.choices,
        default=Manufacturer.OTHER,
    )
    retention_days: int = models.IntegerField(
        choices=RetentionDays.choices,
        default=RetentionDays.SEVEN,
    )
    is_online: bool = models.BooleanField(default=False)
    agent = models.ForeignKey(
        "agents.Agent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cameras",
    )
    tenant = models.ForeignKey(
        "users.Tenant",
        on_delete=models.CASCADE,
        related_name="cameras",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "is_online"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.location})"
