import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone


class StoragePolicy(models.Model):
    """Política de armazenamento por tier — inspirado no Viseron tiered storage.

    Cada tenant pode ter múltiplos tiers por categoria.
    Tier 0 = hot (SSD local), Tier 1 = warm (HDD), Tier 2 = cold (NAS/S3).
    Quando um tier excede max_age ou max_size, arquivos são movidos para o próximo.
    No último tier, arquivos são deletados.
    """

    CATEGORY_CHOICES = [
        ('recordings', 'Gravações (segments)'),
        ('snapshots', 'Snapshots (detecções)'),
        ('heatmaps', 'Mapas de Calor'),
        ('clips', 'Clips de Vídeo'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE, related_name='storage_policies'
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    tier_order = models.IntegerField(default=0)
    path = models.CharField(
        max_length=500,
        help_text='Mount path dentro do container, ex: /app/storage ou /mnt/nas/cold',
    )
    max_age_hours = models.IntegerField(
        null=True, blank=True,
        help_text='Idade máxima em horas. Arquivos mais velhos são movidos/deletados.',
    )
    max_size_gb = models.FloatField(
        null=True, blank=True,
        help_text='Tamanho máximo do tier em GB. Excedente é movido/deletado (FIFO).',
    )
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'storage_policies'
        unique_together = ['tenant', 'category', 'tier_order']
        ordering = ['tenant', 'category', 'tier_order']
        indexes = [
            models.Index(fields=['tenant', 'category', 'enabled']),
        ]

    def __str__(self):
        return f"{self.tenant.name} | {self.category} tier-{self.tier_order}"

    @property
    def max_age_timedelta(self):
        if self.max_age_hours:
            return timedelta(hours=self.max_age_hours)
        return None

    @property
    def max_size_bytes(self):
        if self.max_size_gb:
            return int(self.max_size_gb * 1024 * 1024 * 1024)
        return None


class StorageFile(models.Model):
    """Tracking de arquivos em disco para snapshots, heatmaps, etc.

    Segments já são tracked via modelo Segment.
    Este modelo cobre tudo que antes acumulava sem controle.
    """

    CATEGORY_CHOICES = [
        ('snapshot', 'Snapshot de Detecção'),
        ('heatmap', 'Mapa de Calor'),
        ('clip', 'Clip de Vídeo'),
    ]

    id = models.BigAutoField(primary_key=True)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE, related_name='storage_files'
    )
    camera = models.ForeignKey(
        'cameras.Camera', on_delete=models.CASCADE, related_name='storage_files',
        null=True, blank=True,
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    subcategory = models.CharField(
        max_length=30, blank=True, default='',
        help_text='Ex: lpr, facial, crowd, intrusion, object_detection',
    )
    file_path = models.CharField(max_length=500, unique=True, db_index=True)
    file_size = models.BigIntegerField(default=0)
    tier_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'storage_files'
        indexes = [
            models.Index(fields=['tenant', 'category', 'created_at']),
            models.Index(fields=['camera', 'category', 'subcategory']),
            models.Index(fields=['tier_order', 'created_at']),
        ]

    def __str__(self):
        return f"{self.category}/{self.subcategory} — {self.file_path}"


class Segment(models.Model):
    """Segmento de gravação de vídeo (10 min cada)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    camera = models.ForeignKey('cameras.Camera', on_delete=models.CASCADE, related_name='segments')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField(default=0)
    tier_order = models.IntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'segments'
        indexes = [
            models.Index(fields=['camera', 'start_time']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['tier_order', 'created_at']),
        ]
        ordering = ['start_time']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            retention = getattr(self.camera, 'retention_days', 7)
            self.expires_at = timezone.now() + timedelta(days=retention)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Segment {self.camera.name} [{self.start_time}]"


class Clip(models.Model):
    """Clipe de vídeo gerado pelo usuário"""
    
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('processing', 'Processando'),
        ('completed', 'Concluído'),
        ('failed', 'Falhou'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    camera = models.ForeignKey('cameras.Camera', on_delete=models.CASCADE, related_name='clips')
    name = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    file_path = models.CharField(max_length=500, null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey('auth_app.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clips'
        indexes = [
            models.Index(fields=['camera', 'created_at']),
            models.Index(fields=['status']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.camera.name}"
