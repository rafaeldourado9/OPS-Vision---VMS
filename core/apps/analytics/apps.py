"""AppConfig para analytics."""
from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    """Configuração do app de analytics."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analytics"
    verbose_name = "Analytics"
