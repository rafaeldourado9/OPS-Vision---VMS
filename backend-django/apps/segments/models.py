import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone


class Segment(models.Model):
    """Segmento de gravação de vídeo (10 min cada)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    camera = models.ForeignKey('cameras.Camera', on_delete=models.CASCADE, related_name='segments')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'segments'
        indexes = [
            models.Index(fields=['camera', 'start_time']),
            models.Index(fields=['expires_at']),
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
