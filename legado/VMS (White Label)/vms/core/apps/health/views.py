"""Health check endpoint — sem autenticação."""
import logging

import pika
from django.conf import settings
from django.db import connections
from redis import Redis
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


def _check_db() -> str:
    """Verifica conexão com o PostgreSQL."""
    try:
        connections["default"].ensure_connection()
        return "ok"
    except Exception as exc:
        logger.warning("Health check DB falhou: %s", exc)
        return "error"


def _check_redis() -> str:
    """Verifica conexão com o Redis."""
    try:
        redis_url = settings.REDIS_URL
        client = Redis.from_url(redis_url, socket_connect_timeout=2)
        client.ping()
        return "ok"
    except Exception as exc:
        logger.warning("Health check Redis falhou: %s", exc)
        return "error"


def _check_rabbitmq() -> str:
    """Verifica conexão com o RabbitMQ."""
    try:
        params = pika.URLParameters(settings.RABBITMQ_URL)
        params.socket_timeout = 2
        conn = pika.BlockingConnection(params)
        conn.close()
        return "ok"
    except Exception as exc:
        logger.warning("Health check RabbitMQ falhou: %s", exc)
        return "error"


class HealthCheckView(APIView):
    """GET /api/v1/health/ — sem autenticação requerida."""

    authentication_classes = []
    permission_classes = []

    def get(self, request: Request) -> Response:
        """Retorna status de cada serviço dependente."""
        services = {
            "db": _check_db(),
            "redis": _check_redis(),
            "rabbitmq": _check_rabbitmq(),
        }

        all_ok = all(v == "ok" for v in services.values())
        status_code = 200 if all_ok else 503

        return Response(
            {
                "status": "healthy" if all_ok else "degraded",
                "services": services,
            },
            status=status_code,
        )
