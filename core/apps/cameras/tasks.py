"""Tarefas Celery para câmeras."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="cameras.reprovision_mediamtx", bind=True, max_retries=3, default_retry_delay=15)
def reprovision_mediamtx_task(self) -> dict:
    """Reconcilia paths do MediaMTX com câmeras cadastradas no banco.

    Roda na inicialização e a cada 5 minutos para garantir que câmeras
    não desapareçam após restart do MediaMTX.

    Lógica:
    - Lista paths presentes no MediaMTX
    - Para cada câmera no banco sem path correspondente → registra
    - Não remove paths extras (pode haver streams externos)

    Returns:
        Dict com reprovisioned (int) e errors (int).
    """
    from apps.cameras.models import Camera
    from shared.mediamtx_client import MediaMTXClient, MediaMTXError

    client = MediaMTXClient()

    try:
        existing_paths = {p.name for p in client.list_paths()}
    except MediaMTXError as exc:
        logger.warning("reprovision_mediamtx: não foi possível listar paths — %s", exc)
        raise self.retry(exc=exc)

    cameras = Camera.objects.select_related("agent").all()
    reprovisioned = 0
    errors = 0

    for camera in cameras:
        path_name = f"tenant-{camera.tenant_id}/cam-{camera.id}"
        if path_name in existing_paths:
            continue
        try:
            if camera.agent_id:
                client.add_path(name=path_name)
            else:
                client.add_path(name=path_name, source=camera.rtsp_url)
            reprovisioned += 1
            logger.info("reprovision: path restaurado %s", path_name)
        except MediaMTXError as exc:
            logger.error("reprovision: falha ao restaurar %s — %s", path_name, exc)
            errors += 1

    if reprovisioned:
        logger.info(
            "reprovision_mediamtx: %d paths restaurados, %d erros",
            reprovisioned, errors,
        )

    return {"reprovisioned": reprovisioned, "errors": errors}


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
