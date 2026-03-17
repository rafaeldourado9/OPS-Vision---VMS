"""Models para agents."""
from django.db import models


class Agent(models.Model):
    """Agente local que roda na rede do cliente.

    O agent puxa RTSP das câmeras locais e empurra RTMP para o
    MediaMTX cloud. Todas as conexões são de saída.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"

    name: str = models.CharField(max_length=255)
    api_key: str = models.CharField(max_length=64, unique=True, db_index=True)
    tenant = models.ForeignKey(
        "users.Tenant",
        on_delete=models.CASCADE,
        related_name="agents",
    )
    status: str = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    version: str = models.CharField(max_length=32, blank=True)
    metadata: dict = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"
