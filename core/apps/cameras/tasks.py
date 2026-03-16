"""Tarefas Celery para câmeras."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="cameras.check_online_status")
def check_online_status(camera_id: int) -> bool:
    """Verifica se a câmera está online via MediaMTX.

    Args:
        camera_id: ID da câmera.

    Returns:
        True se a câmera está online.
    """
    from apps.cameras.models import Camera
    from shared.mediamtx_client import MediaMTXClient

    camera = Camera.objects.get(id=camera_id)
    client = MediaMTXClient()

    try:
        paths = client.list_paths()
        path_name = f"tenant-{camera.tenant_id}/cam-{camera.id}"
        is_online = any(p.name == path_name for p in paths)
    except Exception:
        is_online = False

    if camera.is_online != is_online:
        camera.is_online = is_online
        camera.save(update_fields=["is_online"])

    return is_online


@shared_task(name="cameras.health_check_all")
def health_check_all_cameras_task() -> dict:
    """Task periódica que dispara um health check para cada câmera cadastrada.

    Itera sobre todas as câmeras e despacha a sub-task
    cameras.check_online_status para cada uma, permitindo
    processamento paralelo pelo pool de workers.

    Returns:
        Dicionário com o número de câmeras despachadas.
    """
    from apps.cameras.models import Camera

    camera_ids = list(Camera.objects.values_list("id", flat=True))
    for camera_id in camera_ids:
        check_online_status.delay(camera_id)

    logger.info("Health check periódico disparado para %d câmeras.", len(camera_ids))
    return {"cameras_dispatched": len(camera_ids)}


@shared_task(name="cameras.set_online")
def set_camera_online_task(camera_id: int, is_online: bool) -> None:
    """Atualiza o status online/offline de uma câmera.

    Despachado pelo FastAPI quando o MediaMTX reporta on_ready / on_not_ready.

    Args:
        camera_id: ID da câmera.
        is_online: True se conectou, False se desconectou.
    """
    from apps.cameras.models import Camera
    from apps.cameras.services import set_camera_online

    try:
        set_camera_online(camera_id, is_online=is_online)
        logger.info("Câmera %s marcada como %s", camera_id, "online" if is_online else "offline")
    except Camera.DoesNotExist:
        logger.warning("Câmera %s não encontrada ao processar evento online/offline", camera_id)
