"""Lógica de domínio para gravações."""
import os
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from .models import Clip, Recording, RecordingSegment


def start_recording(camera_id: int, tenant_id: int, file_path: str) -> Recording:
    """Inicia uma nova gravação.

    Args:
        camera_id: ID da câmera.
        tenant_id: ID do tenant.
        file_path: Caminho do arquivo de gravação.

    Returns:
        Recording criada com status RECORDING.
    """
    return Recording.objects.create(
        camera_id=camera_id,
        tenant_id=tenant_id,
        file_path=file_path,
        started_at=timezone.now(),
    )


def stop_recording(recording_id: int) -> Recording:
    """Finaliza uma gravação.

    Args:
        recording_id: ID da gravação.

    Returns:
        Recording atualizada com status COMPLETED.
    """
    recording = Recording.objects.get(id=recording_id)
    recording.status = Recording.Status.COMPLETED
    recording.ended_at = timezone.now()
    recording.save(update_fields=["status", "ended_at"])
    return recording


def get_camera_timeline(camera_id: int, start: datetime, end: datetime) -> QuerySet[RecordingSegment]:
    """Recupera os segmentos de gravação que compõem a linha do tempo da câmera.
    
    Os segmentos retornados interceptam a janela temporal solicitada:
    start_time <= end AND end_time >= start.
    
    Args:
        camera_id: ID da câmera.
        start: Início do período (datetime).
        end: Fim do período (datetime).
        
    Returns:
        QuerySet de RecordingSegment ordenado por start_time.
    """
    return RecordingSegment.objects.filter(
        camera_id=camera_id,
        start_time__lte=end,
        end_time__gte=start,
    ).order_by("start_time")


def get_playback_segment(camera_id: int, timestamp: datetime) -> RecordingSegment | None:
    """Localiza o segmento de gravação que contém o timestamp solicitado.

    Args:
        camera_id: ID da câmera.
        timestamp: Momento exato para buscar (datetime).

    Returns:
        RecordingSegment ou None se não encontrar.
    """
    return RecordingSegment.objects.filter(
        camera_id=camera_id,
        start_time__lte=timestamp,
        end_time__gte=timestamp,
    ).first()


# Lazy import — will be replaced by the real Celery task at runtime
# Tests can mock this via "apps.recordings.services.generate_clip_task"
generate_clip_task = None


def _get_generate_clip_task():
    global generate_clip_task
    if generate_clip_task is None:
        from apps.recordings.tasks import generate_clip_task as task
        generate_clip_task = task
    return generate_clip_task


def create_clip_from_event(event) -> Clip:
    """Cria um Clip a partir de um evento e despacha a geração assíncrona.

    Clip window: 10s antes do evento, 20s após o evento.

    Args:
        event: Instância do Event.

    Returns:
        Clip criado com status PENDING.
    """
    clip_start = event.created_at - timedelta(seconds=10)
    clip_end = event.created_at + timedelta(seconds=20)

    clip = Clip.objects.create(
        tenant=event.tenant,
        camera=event.camera,
        event=event,
        start_time=clip_start,
        end_time=clip_end,
        status=Clip.Status.PENDING,
    )

    _get_generate_clip_task().delay(clip.id)

    return clip


def create_clip(
    camera_id: int,
    tenant_id: int,
    start_time: datetime,
    end_time: datetime,
) -> Clip:
    """Cria um Clip diretamente a partir de um intervalo de tempo.

    Usado quando o operador seleciona um range na linha do tempo,
    sem vínculo com um evento específico.

    Args:
        camera_id: ID da câmera.
        tenant_id: ID do tenant.
        start_time: Início do clip.
        end_time: Fim do clip.

    Returns:
        Clip criado com status PENDING.
    """
    clip = Clip.objects.create(
        tenant_id=tenant_id,
        camera_id=camera_id,
        start_time=start_time,
        end_time=end_time,
        status=Clip.Status.PENDING,
    )
    _get_generate_clip_task().delay(clip.id)
    return clip


def get_tenant_storage_bytes(tenant_id: int) -> int:
    """Calcula o total de bytes usados em disco por um tenant.

    Soma o tamanho dos arquivos de todos os RecordingSegments e Clips
    do tenant que existem no disco. Ignora arquivos ausentes.

    Args:
        tenant_id: ID do tenant.

    Returns:
        Total de bytes em uso.
    """
    total = 0

    segments = RecordingSegment.objects.filter(
        tenant_id=tenant_id,
    ).values_list("file_path", flat=True)

    for path in segments:
        if path and os.path.exists(path):
            total += os.path.getsize(path)

    clips = Clip.objects.filter(
        tenant_id=tenant_id,
        status=Clip.Status.READY,
    ).values_list("file_path", flat=True)

    for path in clips:
        if path and os.path.exists(path):
            total += os.path.getsize(path)

    return total


def check_storage_quota(tenant_id: int) -> dict:
    """Verifica o uso de storage de um tenant contra a quota configurada.

    Args:
        tenant_id: ID do tenant.

    Returns:
        Dicionário com used_bytes, quota_bytes, usage_ratio e over_quota.
    """
    quota_bytes = settings.STORAGE_QUOTA_BYTES_PER_TENANT
    used_bytes = get_tenant_storage_bytes(tenant_id)
    usage_ratio = used_bytes / quota_bytes if quota_bytes > 0 else 0.0

    return {
        "used_bytes": used_bytes,
        "quota_bytes": quota_bytes,
        "usage_ratio": round(usage_ratio, 4),
        "over_quota": used_bytes > quota_bytes,
    }


def cleanup_old_recordings() -> dict:
    """Apaga os arquivos físicos e registros de banco de segmentos antigos.

    A retenção é baseada no 'retention_days' de cada câmera individualmente.

    Returns:
        Um dict com as estatísticas de limpeza, por exemplo:
        {"cameras_processed": X, "segments_deleted": Y, "errors": Z}
    """
    import os
    from apps.cameras.models import Camera
    import logging

    logger = logging.getLogger(__name__)

    stats = {
        "cameras_processed": 0,
        "segments_deleted": 0,
        "errors": 0,
    }

    cameras = Camera.objects.all()
    now = timezone.now()

    for camera in cameras:
        try:
            stats["cameras_processed"] += 1
            retention = camera.retention_days
            if not retention or retention <= 0:
                continue

            cutoff_date = now - timedelta(days=retention)

            old_segments = RecordingSegment.objects.filter(
                camera=camera,
                end_time__lt=cutoff_date,
            )

            # Usar count e iterate ao invés de bulk action pura
            # porque precisamos apagar o arquivo no disco também
            deleted_count = 0
            for seg in old_segments:
                try:
                    if seg.file_path and os.path.exists(seg.file_path):
                        os.remove(seg.file_path)
                except Exception as e:
                    logger.error(f"Erro ao deletar arquivo {seg.file_path}: {e}")
                    # Continua mesmo se falhar ao apagar arquivo para apagar o DB do mesmo jeito
                
                seg.delete()
                deleted_count += 1

            stats["segments_deleted"] += deleted_count
            if deleted_count > 0:
                logger.info(f"Câmera {camera.id}: {deleted_count} segmentos deletados (retenção: {retention} dias).")
                
        except Exception as err:
            logger.error(f"Erro ao processar limpeza da câmera {camera.id}: {err}")
            stats["errors"] += 1

    return stats
