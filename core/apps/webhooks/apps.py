"""AppConfig para webhooks."""
from django.apps import AppConfig


class WebhooksConfig(AppConfig):
    """Configuração do app de webhooks."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.webhooks"
    verbose_name = "Webhooks"
