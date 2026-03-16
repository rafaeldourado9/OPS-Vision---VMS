"""Configuração do app notifications."""
import threading

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Configuração do app de notificações."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    verbose_name = "Notificações"

    def ready(self):
        """Inicializa resources do app (ex: RabbitMQ consumers)."""
        import sys
        
        # Só inicia consumers reais se rodando Celery worker
        if "celery" in sys.argv[0]:
            thread = threading.Thread(
                target=self._start_consumers,
                daemon=True,
            )
            thread.start()

    @staticmethod
    def _start_consumers():
        from .consumers import start_notification_consumers
        start_notification_consumers()
