"""Models para analytics — ROI, DwellEvent, FaceProfile e FaceDetectionEvent."""
from django.db import models


class RegionOfInterest(models.Model):
    """Zona de análise desenhada sobre uma câmera."""

    class IAType(models.TextChoices):
        VEHICLE_DWELL = "vehicle_dwell", "Permanência Veicular"
        INTRUSION = "intrusion", "Intrusão"
        OBJECT_DETECTED = "object_detected", "Detecção de Objetos"
        CROWD = "crowd", "Multidão"
        VEHICLE_TRAFFIC = "vehicle_traffic", "Tráfego Veicular"
        HUMAN_TRAFFIC = "human_traffic", "Tráfego Humano"
        LINE_CROSSING = "line_crossing", "Cruzamento de Linha"
        LOITERING = "loitering", "Perambulação"
        ABANDONED_OBJECT = "abandoned_object", "Objeto Abandonado"
        QUEUE = "queue", "Fila"
        HEATMAP = "heatmap", "Mapa de Calor"
        LPR = "lpr", "Reconhecimento de Placa"
        FACIAL = "facial", "Reconhecimento Facial"

    camera = models.ForeignKey(
        "cameras.Camera",
        on_delete=models.CASCADE,
        related_name="rois",
    )
    tenant = models.ForeignKey(
        "users.Tenant",
        on_delete=models.CASCADE,
        related_name="rois",
    )
    name = models.CharField(max_length=100)
    ia_type = models.CharField(
        max_length=30,
        choices=IAType.choices,
        default=IAType.INTRUSION,
    )
    # Lista de pontos [[x, y], ...] normalizados 0.0–1.0
    polygon_points = models.JSONField(default=list)
    # Parâmetros específicos do tipo (threshold, classes, etc.)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["camera", "is_active"]),
            models.Index(fields=["tenant", "ia_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.ia_type}) — {self.camera}"


class DwellEvent(models.Model):
    """Evento de permanência veicular registrado pelo plugin vehicle_dwell."""

    camera = models.ForeignKey(
        "cameras.Camera",
        on_delete=models.CASCADE,
        related_name="dwell_events",
    )
    tenant = models.ForeignKey(
        "users.Tenant",
        on_delete=models.CASCADE,
        related_name="dwell_events",
    )
    roi = models.ForeignKey(
        RegionOfInterest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dwell_events",
    )
    # ID atribuído pelo tracker (ByteTrack)
    track_id = models.IntegerField()
    entered_at = models.DateTimeField()
    exited_at = models.DateTimeField(null=True, blank=True)
    dwell_seconds = models.IntegerField(null=True, blank=True)
    # Snapshot do frame no momento da entrada
    frame_path = models.CharField(max_length=512, blank=True)
    # Clip gerado (FK para recordings.Clip)
    clip = models.ForeignKey(
        "recordings.Clip",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dwell_events",
    )
    # True = permanência entre 60-240s, False = fora do range, None = em andamento
    is_valid = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-entered_at"]
        indexes = [
            models.Index(fields=["camera", "-entered_at"]),
            models.Index(fields=["tenant", "is_valid"]),
            models.Index(fields=["tenant", "-entered_at"]),
        ]

    def __str__(self) -> str:
        status = "em andamento" if self.exited_at is None else f"{self.dwell_seconds}s"
        return f"Track {self.track_id} — {self.camera} — {status}"


class FaceProfile(models.Model):
    """Rosto cadastrado para reconhecimento facial.

    ⚠ LGPD: armazena biometria. Requer consentimento explícito.
    Só pode ser criado quando tenant.facial_recognition_enabled=True.
    Deletável integralmente via endpoint por CPF.
    """

    name = models.CharField(max_length=255, help_text="Nome completo da pessoa.")
    cpf = models.CharField(
        max_length=14, blank=True,
        help_text="CPF para direito de exclusão LGPD (formato: 000.000.000-00).",
    )
    notes = models.TextField(blank=True, help_text="Observações (cargo, acesso, etc.).")
    # Embedding ArcFace 512-dim normalizado — list[float]
    embedding = models.JSONField(help_text="Vetor de embedding facial 512-dim (ArcFace).")
    # Caminho do snapshot de enrolamento
    photo_path = models.CharField(max_length=512, blank=True)
    tenant = models.ForeignKey(
        "users.Tenant",
        on_delete=models.CASCADE,
        related_name="face_profiles",
    )
    lgpd_consent = models.BooleanField(
        default=False,
        help_text="Consentimento explícito do titular para uso biométrico.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["tenant", "cpf"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} (tenant={self.tenant_id})"


class FaceDetectionEvent(models.Model):
    """Evento de detecção/reconhecimento facial registrado pelo plugin."""

    camera = models.ForeignKey(
        "cameras.Camera",
        on_delete=models.CASCADE,
        related_name="face_events",
    )
    tenant = models.ForeignKey(
        "users.Tenant",
        on_delete=models.CASCADE,
        related_name="face_events",
    )
    roi = models.ForeignKey(
        RegionOfInterest,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="face_events",
    )
    # Perfil identificado — None = rosto desconhecido
    face_profile = models.ForeignKey(
        FaceProfile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="detection_events",
    )
    # Similaridade coseno com o melhor match (0.0–1.0)
    confidence = models.FloatField(default=0.0)
    is_unknown = models.BooleanField(
        default=False,
        help_text="True = rosto não identificado na base de cadastros.",
    )
    frame_path = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "-created_at"]),
            models.Index(fields=["camera", "-created_at"]),
            models.Index(fields=["tenant", "is_unknown"]),
        ]

    def __str__(self) -> str:
        who = self.face_profile.name if self.face_profile else "Desconhecido"
        return f"{who} — cam={self.camera_id} conf={self.confidence:.2f}"
