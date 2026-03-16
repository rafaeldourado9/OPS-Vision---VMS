"""Handlers de webhooks recebidos."""
from typing import Any

from .models import WebhookLog


def log_webhook(
    source: str,
    endpoint: str,
    payload: dict[str, Any],
) -> WebhookLog:
    """Registra um webhook recebido no log.

    Args:
        source: Origem do webhook (alpr, mediamtx, etc.).
        endpoint: Endpoint que recebeu o webhook.
        payload: Dados recebidos.

    Returns:
        Log do webhook criado.
    """
    return WebhookLog.objects.create(
        source=source,
        endpoint=endpoint,
        payload=payload,
    )
