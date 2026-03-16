"""Tarefas Celery para analytics (despacho para plugins)."""
from celery import shared_task


@shared_task(name="analytics.process_frame")
def process_frame_task(
    plugin_name: str,
    frame_data: bytes,
    camera_id: int,
    tenant_id: int,
) -> dict | None:
    """Despacha um frame para um plugin de analytics.

    Args:
        plugin_name: Nome do plugin.
        frame_data: Bytes do frame.
        camera_id: ID da câmera.
        tenant_id: ID do tenant.

    Returns:
        Resultado do plugin ou None.
    """
    # TODO: carregar plugin e processar frame
    return None
