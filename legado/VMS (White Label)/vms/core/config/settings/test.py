"""Settings para testes."""
from .base import *  # noqa: F401, F403

DEBUG = True
SECRET_KEY = "test-secret-key-not-for-production"

# SQLite in-memory para testes rápidos
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Desabilita password validators em testes
AUTH_PASSWORD_VALIDATORS = []

# Cache em memória local para testes
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Celery síncrono em testes
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Em testes, force_authenticate do DRF bypassa JWT
# Mantém SessionAuth para testes que verificam 401
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",
        "user": "120/minute",
        "auth_anon": "5/minute",
        "auth_user": "60/minute",
    },
}
