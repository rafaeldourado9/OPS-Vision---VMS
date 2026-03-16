"""Settings de desenvolvimento."""
from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# CORS permissivo em dev
CORS_ALLOW_ALL_ORIGINS = True

# Logging visível em dev (especialmente Celery worker)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
