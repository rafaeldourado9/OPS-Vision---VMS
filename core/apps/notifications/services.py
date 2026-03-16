import fnmatch
import logging
from typing import Any

from celery import current_app

from .models import NotificationRule

from .models import NotificationRule

logger = logging.getLogger(__name__)


def evaluate_notification_rules(
    event_type: str,
    tenant_id: int,
    payload: dict[str, Any],
) -> None:
    """Avalia quais regras se aplicam a um evento e despacha notificações.

    Usa `fnmatch` para comparar `event_type` com `event_type_pattern`.
    Ex: "camera.online" dá match em "camera.*".

    Args:
        event_type: Tipo do evento disparado.
        tenant_id: ID do tenant dono do evento.
        payload: Dados do evento.
    """
    try:
        rules = NotificationRule.objects.filter(
            tenant_id=tenant_id,
            is_active=True,
        )

        matched_rules = []
        for rule in rules:
            if fnmatch.fnmatch(event_type, rule.event_type_pattern):
                matched_rules.append(rule)

        if not matched_rules:
            logger.debug(
                "Nenhuma regra correspondente para evento %s no tenant %d",
                event_type,
                tenant_id,
            )
            return

        for rule in matched_rules:
            if rule.channel == NotificationRule.Channel.WEBHOOK:
                event_id = payload.get("id") or payload.get("event_id")
                try:
                    event_id = int(event_id) if event_id else None
                except (ValueError, TypeError):
                    event_id = None

                logger.info(
                    "Despachando webhook para regra %d (%s) -> %s",
                    rule.id,
                    rule.name,
                    event_type,
                )
                current_app.send_task(
                    "notifications.send_webhook",
                    kwargs={
                        "rule_id": rule.id,
                        "event_type": event_type,
                        "event_id": event_id,
                        "payload": payload,
                    }
                )

    except Exception:
        logger.exception("Erro ao avaliar regras de notificação")
