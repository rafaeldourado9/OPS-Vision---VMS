"""Signals para o app de eventos."""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from shared import pubsub

from .models import Event

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Event)
def publish_event_to_realtime(sender, instance: Event, created: bool, **kwargs) -> None:
    """Publica novo evento no canal Redis vms:realtime.

    Chamado automaticamente após qualquer Event.objects.create().
    Falhas são silenciosas para não quebrar o fluxo de criação.

    Args:
        sender: Classe Event.
        instance: Instância do evento salvo.
        created: True apenas para novos eventos.
    """
    if not created:
        return

    pubsub.publish(
        "vms:realtime",
        {
            "type": "new_event",
            "event_id": instance.id,
            "event_type": instance.event_type,
            "camera_id": instance.camera_id,
            "tenant_id": instance.tenant_id,
        },
    )
