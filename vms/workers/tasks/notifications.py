"""Tarefas Celery para notificações."""
import hashlib
import hmac
import json
import logging

import httpx
from celery import shared_task

from apps.notifications.models import NotificationLog, NotificationRule

logger = logging.getLogger(__name__)


def _compute_hmac_signature(secret: str, payload: dict) -> str:
    """Computa HMAC-SHA256 do payload JSON."""
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()


@shared_task(name="notifications.send_webhook", max_retries=3)
def send_webhook_notification(
    rule_id: int,
    event_type: str,
    event_id: int | None,
    payload: dict,
) -> bool:
    """Envia notificação via webhook e registra em NotificationLog.

    Args:
        rule_id: ID da regra de notificação associada.
        event_type: Tipo do evento original.
        event_id: ID do evento no banco (se aplicável).
        payload: Dados da notificação em JSON.

    Returns:
        True se enviou com sucesso (HTTP 2xx).
    """
    try:
        rule = NotificationRule.objects.get(id=rule_id)
    except NotificationRule.DoesNotExist:
        logger.error("Regra %d não encontrada", rule_id)
        return False

    status_str = "failed"
    response_code = None
    response_body = ""

    try:
        # Envio síncrono (tá rodando em worker Celery, thread bloqueante é ok)
        with httpx.Client(timeout=5.0) as client:
            headers = {"Content-Type": "application/json"}
            if rule.webhook_secret:
                headers["X-VMS-Signature"] = _compute_hmac_signature(
                    rule.webhook_secret, payload
                )
            response = client.post(
                rule.destination,
                json=payload,
                headers=headers,
            )
            response_code = response.status_code
            response_body = response.text[:1000]  # Limita tamanho log

            if response.is_success:
                status_str = "success"
                logger.info("Webhook regra %d enviado com sucesso", rule_id)
            else:
                logger.warning(
                    "Webhook regra %d falhou com %d: %s",
                    rule_id,
                    response_code,
                    response_body,
                )

    except httpx.TimeoutException:
        response_body = "Timeout (5s)"
        logger.warning("Timeout ao enviar webhook da regra %d", rule_id)
    except Exception as exc:
        response_body = str(exc)[:1000]
        logger.error("Erro inesperado webhook regra %d: %s", rule_id, exc)

    # Registra no log
    NotificationLog.objects.create(
        rule=rule,
        event_id=event_id,
        event_type=event_type,
        status=status_str,
        response_code=response_code,
        response_body=response_body,
    )

    return status_str == "success"


@shared_task(name="notifications.send_push")
def send_push_notification(
    user_id: int,
    title: str,
    body: str,
) -> bool:
    """Envia push notification para um usuário.

    Args:
        user_id: ID do usuário.
        title: Título da notificação.
        body: Corpo da notificação.

    Returns:
        True se enviou com sucesso.
    """
    # TODO: implementar push notification
    return True
