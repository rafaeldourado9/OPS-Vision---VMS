"""Config package — exporta Celery app para autodiscovery."""
try:
    from .celery import app as celery_app

    __all__ = ["celery_app"]
except ImportError:
    pass
