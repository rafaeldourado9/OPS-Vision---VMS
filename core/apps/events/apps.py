"""AppConfig para events."""
from django.apps import AppConfig


class EventsConfig(AppConfig):
    """Configuração do app de eventos."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.events"
    verbose_name = "Eventos"

    def ready(self) -> None:
        """Registra signals ao inicializar o app."""
        import apps.events.signals  # noqa: F401
