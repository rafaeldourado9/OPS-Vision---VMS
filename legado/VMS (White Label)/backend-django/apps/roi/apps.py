from django.apps import AppConfig


class RoiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.roi'

    def ready(self):
        import apps.roi.signals  # noqa: F401
