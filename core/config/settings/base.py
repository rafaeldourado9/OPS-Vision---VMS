"""Settings base — compartilhado por todos os ambientes."""
import os
from pathlib import Path

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Security
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "INSECURE-change-me")
DEBUG = False
ALLOWED_HOSTS: list[str] = []

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "django_filters",
    # Local
    "apps.users",
    "apps.cameras",
    "apps.events",
    "apps.recordings",
    "apps.webhooks",
    "apps.notifications",
    "apps.agents",
    "apps.health",
    "apps.analytics",
]

# Adiciona corsheaders se disponível
try:
    import corsheaders  # noqa: F401

    INSTALLED_APPS.insert(INSTALLED_APPS.index("rest_framework") + 1, "corsheaders")
    _has_cors = True
except ImportError:
    _has_cors = False

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    *(["corsheaders.middleware.CorsMiddleware"] if _has_cors else []),
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "vms"),
        "USER": os.environ.get("POSTGRES_USER", "vms"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "vmsdev"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# Auth
AUTH_USER_MODEL = "users.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

# Internationalization
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "static/"

# Default primary key
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# REST Framework
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
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",
        "user": "120/minute",
        "auth_anon": "5/minute",
        "auth_user": "60/minute",
    },
}

# JWT
from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "SIGNING_KEY": os.environ.get("JWT_SECRET", SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# CORS
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000"
).split(",")

# MediaMTX
MEDIAMTX_API_URL = os.environ.get("MEDIAMTX_API_URL", "http://mediamtx:9997")
MEDIAMTX_STREAM_BASE_URL = os.environ.get(
    "MEDIAMTX_STREAM_BASE_URL", "http://mediamtx:8889"
)
MEDIAMTX_API_USER = os.environ.get("MEDIAMTX_API_USER", "mediamtx_api_user")
MEDIAMTX_API_PASSWORD = os.environ.get("MEDIAMTX_API_PASSWORD", "GtV!sionMed1aMTX$2025")
# URL pública RTMP — domínio/IP público do servidor, exibido ao operador
# Ex: rtmp://cameras.suaempresa.com:1935
MEDIAMTX_RTMP_URL = os.environ.get("MEDIAMTX_RTMP_URL", "rtmp://localhost:1935")

# Segredo para geração do token HMAC de autenticação RTMP push
# Deve ser longo e aleatório. Mesmo valor deve estar no container fastapi.
MEDIAMTX_PUBLISH_SECRET = os.environ.get("MEDIAMTX_PUBLISH_SECRET", "")
# URLs públicas (acessíveis pelo browser/frontend)
MEDIAMTX_HLS_BASE_URL = os.environ.get("MEDIAMTX_HLS_BASE_URL", "http://localhost:8888")
MEDIAMTX_WEBRTC_BASE_URL = os.environ.get("MEDIAMTX_WEBRTC_BASE_URL", "http://localhost:8889")

# Stream tokens (acesso autenticado a streams HLS/WebRTC)
STREAM_TOKEN_TTL_SECONDS = int(os.environ.get("STREAM_TOKEN_TTL_SECONDS", "1800"))

# RabbitMQ
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "vms")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "vmsdev")
# pika requires /%2F for vhost /
RABBITMQ_URL = (
    f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}"
    f"@{RABBITMQ_HOST}:{RABBITMQ_PORT}/%2F"
)

# Redis
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# Celery — kombu handles // as vhost /
CELERY_BROKER_URL = (
    f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}"
    f"@{RABBITMQ_HOST}:{RABBITMQ_PORT}//"
)
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_REDIRECT_STDOUTS = True

# Recordings
RECORDINGS_PATH = os.environ.get("RECORDINGS_PATH", "/data/recordings")

# ALPR
ALPR_LOW_CONFIDENCE_THRESHOLD = float(
    os.environ.get("ALPR_LOW_CONFIDENCE_THRESHOLD", "0.7")
)
ALPR_DEDUP_TTL_SECONDS = int(
    os.environ.get("ALPR_DEDUP_TTL_SECONDS", "60")
)

# Storage quota (por tenant)
STORAGE_QUOTA_BYTES_PER_TENANT = int(
    os.environ.get("STORAGE_QUOTA_BYTES_PER_TENANT", str(100 * 1024 ** 3))  # 100 GB
)
STORAGE_QUOTA_WARN_THRESHOLD = float(
    os.environ.get("STORAGE_QUOTA_WARN_THRESHOLD", "0.8")  # 80%
)

# JWT
JWT_SECRET = os.environ.get("JWT_SECRET", "INSECURE-change-me")

# Analytics Service — chave interna para o serviço de analytics se autenticar
ANALYTICS_SERVICE_API_KEY = os.environ.get("ANALYTICS_SERVICE_API_KEY", "")
