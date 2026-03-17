"""AppConfig para cameras."""
from django.apps import AppConfig


class CamerasConfig(AppConfig):
    """Configuração do app de câmeras."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cameras"
    verbose_name = "Câmeras"
