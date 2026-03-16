"""App config para agents."""
from django.apps import AppConfig


class AgentsConfig(AppConfig):
    """Configuração do app agents."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.agents"
    verbose_name = "Agents"
