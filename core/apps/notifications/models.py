"""Modelos para o sistema de notificações."""
from django.db import models

from apps.users.models import Tenant


class NotificationRule(models.Model):
    """Regra de notificação baseada em eventos."""

    class Channel(models.TextChoices):
        """Canais de notificação suportados."""

        WEBHOOK = "webhook", "Webhook"
        # EMAIL = "email", "E-mail"  # Para uso futuro

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="notification_rules",
        help_text="Tenant dono desta regra.",
    )
    name = models.CharField(
        max_length=255,
        help_text="Nome descritivo da regra.",
    )
    event_type_pattern = models.CharField(
        max_length=255,
        help_text="Padrão do evento (ex: 'detection.alpr', 'camera.*').",
    )
    channel = models.CharField(
        max_length=50,
        choices=Channel.choices,
        default=Channel.WEBHOOK,
        help_text="Canal de entrega.",
    )
    destination = models.CharField(
        max_length=1000,
        help_text="URL do webhook ou endereço de destino.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Se a regra está ativa para novos eventos.",
    )
    webhook_secret = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Chave secreta para assinar webhooks com HMAC-SHA256.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notifications_rule"
        verbose_name = "Regra de Notificação"
        verbose_name_plural = "Regras de Notificação"
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.event_type_pattern} -> {self.channel})"


class NotificationLog(models.Model):
    """Log de disparo de uma notificação."""

    rule = models.ForeignKey(
        NotificationRule,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    event_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="ID do evento original se houver relacionamento no BD.",
    )
    event_type = models.CharField(
        max_length=255,
        help_text="Tipo de evento real que disparou (ex: 'detection.alpr').",
    )
    status = models.CharField(
        max_length=50,
        help_text="'success' ou 'failed'.",
    )
    response_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="Código HTTP retornado pelo webhook.",
    )
    response_body = models.TextField(
        blank=True,
        help_text="Corpo da resposta do destinatário.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications_log"
        verbose_name = "Log de Notificação"
        verbose_name_plural = "Logs de Notificação"
        indexes = [
            models.Index(fields=["rule", "-created_at"]),
        ]

    def __str__(self):
        return f"Log {self.id} for Rule {self.rule_id} ({self.status})"
