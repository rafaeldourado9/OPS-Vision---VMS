"""Abstração de pub/sub Redis para comunicação em tempo real."""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_redis_client = None


def _get_client():
    """Retorna cliente Redis (singleton lazy)."""
    global _redis_client
    if _redis_client is None:
        import redis
        from django.conf import settings

        _redis_client = redis.from_url(settings.REDIS_URL)
    return _redis_client


def publish(channel: str, data: dict[str, Any]) -> None:
    """Publica mensagem JSON no canal Redis.

    Falhas são logadas mas não propagadas para não quebrar o fluxo principal.

    Args:
        channel: Nome do canal (ex: "vms:realtime").
        data: Dicionário a ser serializado como JSON.
    """
    try:
        _get_client().publish(channel, json.dumps(data))
    except Exception as exc:
        logger.warning("Falha ao publicar no Redis canal %s: %s", channel, exc)
