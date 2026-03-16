"""AppConfig para recordings."""
from django.apps import AppConfig


class RecordingsConfig(AppConfig):
    """Configuração do app de gravações."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.recordings"
    verbose_name = "Gravações"
