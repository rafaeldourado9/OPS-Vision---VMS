from django.apps import AppConfig


class CamerasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cameras'

    def ready(self):
        import apps.cameras.signals  # noqa
