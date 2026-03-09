import uuid
from django.db import models


class AuditLog(models.Model):
    """Log de auditoria imutável para ações do super admin"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'auth_app.User', on_delete=models.CASCADE, related_name='audit_logs'
    )
    action = models.CharField(max_length=100)
    target_tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_logs'
    )
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.action} by {self.user.email} at {self.created_at}"
