"""Models para gravações."""
from django.db import models


class Recording(models.Model):
    """Gravação de vídeo de uma câmera."""

    class Status(models.TextChoices):
        RECORDING = "recording", "Gravando"
        COMPLETED = "completed", "Concluída"
        FAILED = "failed", "Falhou"

    camera = models.ForeignKey(
        "cameras.Camera",
        on_delete=models.CASCADE,
        related_name="recordings",
    )
    tenant = models.ForeignKey(
        "users.Tenant",
        on_delete=models.CASCADE,
        related_name="recordings",
    )
    file_path: str = models.CharField(max_length=500)
    status: str = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RECORDING,
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    file_size_bytes = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["camera", "-started_at"]),
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self) -> str:
        return f"Recording {self.camera} @ {self.started_at:%Y-%m-%d %H:%M}"


class RecordingSegment(models.Model):
    """Indexa um arquivo contínuo de vídeo segmentado pelo MediaMTX."""

    camera = models.ForeignKey(
        "cameras.Camera",
        on_delete=models.CASCADE,
        related_name="segments",
    )
    tenant = models.ForeignKey(
        "users.Tenant",
        on_delete=models.CASCADE,
    )
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)
    duration_seconds = models.IntegerField(default=0)
    file_path = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_time"]
        indexes = [
            models.Index(fields=["camera", "start_time"]),
            models.Index(fields=["camera", "end_time"]),
            models.Index(fields=["tenant", "start_time"]),
        ]

    def __str__(self) -> str:
        return f"Segment {self.camera.name}: {self.start_time:%H:%M:%S} - {self.end_time:%H:%M:%S}"


class Clip(models.Model):
    """Controla clips exportados vinculados ou não a um evento."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        PROCESSING = "processing", "Processando"
        READY = "ready", "Pronto"
        FAILED = "failed", "Falha"

    tenant = models.ForeignKey(
        "users.Tenant",
        on_delete=models.CASCADE,
    )
    camera = models.ForeignKey(
        "cameras.Camera",
        on_delete=models.CASCADE,
    )
    event = models.ForeignKey(
        "events.Event",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    file_path = models.CharField(max_length=500, null=True, blank=True)
    status: str = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["camera", "start_time", "end_time"]),
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self) -> str:
        return f"Clip {self.id} ({self.status}) - {self.camera.name}"
