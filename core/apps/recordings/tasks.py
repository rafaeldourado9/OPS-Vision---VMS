"""Tarefas Celery para gravações."""
import json
import logging
import subprocess
from datetime import datetime, timedelta

from celery import shared_task
from django.utils import timezone

from apps.cameras.models import Camera
from apps.recordings.models import Clip, RecordingSegment

logger = logging.getLogger(__name__)


@shared_task(name="recordings.process_segment")
def process_recording_segment_task(mediamtx_path: str, file_path: str) -> bool:
    """Extrai duração via ffprobe e indexa o segmento na tabela RecordingSegment.

    Args:
        mediamtx_path: Path no formato "tenant-<id>/cam-<id>".
        file_path: Caminho absoluto do arquivo MP4 gravado.

    Returns:
        True se indexado com sucesso.

    Raises:
        ValueError: Se o formato do path for inválido.
        Exception: Se a câmera não for encontrada ou o ffprobe falhar.
    """
    try:
        parts = mediamtx_path.split("/")
        if (
            len(parts) != 2
            or not parts[0].startswith("tenant-")
            or not parts[1].startswith("cam-")
        ):
            raise ValueError("Invalid mediamtx path format")
        tenant_id = int(parts[0].replace("tenant-", ""))
        camera_id = int(parts[1].replace("cam-", ""))
    except ValueError:
        raise
    except Exception as e:
        logger.error("Erro ao parsear path %s: %s", mediamtx_path, e)
        raise ValueError("Invalid mediamtx path format") from e

    try:
        camera = Camera.objects.get(id=camera_id, tenant_id=tenant_id)
    except Camera.DoesNotExist:
        logger.error(
            "Câmera %s ou tenant %s do path %s não encontrada",
            camera_id, tenant_id, mediamtx_path,
        )
        raise Exception("Camera not found")

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        file_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("FFprobe falhou em %s", file_path)
        raise Exception(f"Failed to probe video file: {result.stderr}")

    probe_data = json.loads(result.stdout)
    format_info = probe_data.get("format", {})
    duration_seconds = float(format_info.get("duration", 0.0))

    tags = format_info.get("tags", {})
    creation_time_str = tags.get("creation_time")

    if creation_time_str:
        end_time = datetime.fromisoformat(creation_time_str.replace("Z", "+00:00"))
    else:
        import os
        end_time = datetime.fromtimestamp(os.stat(file_path).st_mtime, tz=timezone.utc)

    start_time = end_time - timedelta(seconds=duration_seconds)

    RecordingSegment.objects.create(
        camera=camera,
        tenant=camera.tenant,
        start_time=start_time,
        end_time=end_time,
        duration_seconds=int(round(duration_seconds)),
        file_path=file_path,
    )
    logger.info(
        "Segmento %s (%ds) indexado para câmera %s.",
        file_path, int(round(duration_seconds)), camera_id,
    )
    return True


@shared_task(name="recordings.generate_clip")
def generate_clip_task(clip_id: int) -> bool:
    """Gera um clip de vídeo a partir dos segmentos de gravação.

    Usa ffmpeg com stream copy (sem re-encode) para máxima performance.

    Args:
        clip_id: ID do Clip a ser gerado.

    Returns:
        True se gerado com sucesso.
    """
    import os
    import tempfile

    try:
        clip = Clip.objects.get(id=clip_id)
        clip.status = Clip.Status.PROCESSING
        clip.save(update_fields=["status"])

        segments = RecordingSegment.objects.filter(
            camera_id=clip.camera_id,
            start_time__lte=clip.end_time,
            end_time__gte=clip.start_time,
        ).order_by("start_time")

        if not segments.exists():
            logger.warning("Clip %s: nenhum segmento encontrado", clip_id)
            clip.status = Clip.Status.FAILED
            clip.save(update_fields=["status"])
            return False

        output_dir = f"/recordings/clips/{clip.tenant_id}"
        os.makedirs(output_dir, exist_ok=True)
        output_path = f"{output_dir}/clip_{clip_id}.mp4"

        segment_list = list(segments)

        if len(segment_list) == 1:
            seg = segment_list[0]
            ss = max(0, (clip.start_time - seg.start_time).total_seconds())
            duration = (clip.end_time - clip.start_time).total_seconds()
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(ss),
                "-i", seg.file_path,
                "-t", str(duration),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                output_path,
            ]
        else:
            concat_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False
            )
            try:
                for seg in segment_list:
                    concat_file.write(f"file '{seg.file_path}'\n")
                concat_file.close()

                ss = max(0, (clip.start_time - segment_list[0].start_time).total_seconds())
                duration = (clip.end_time - clip.start_time).total_seconds()

                cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_file.name,
                    "-ss", str(ss),
                    "-t", str(duration),
                    "-c", "copy",
                    "-avoid_negative_ts", "make_zero",
                    output_path,
                ]
            finally:
                os.unlink(concat_file.name)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("FFmpeg falhou para clip %s: %s", clip_id, result.stderr)
            clip.status = Clip.Status.FAILED
            clip.save(update_fields=["status"])
            return False

        clip.file_path = output_path
        clip.status = Clip.Status.READY
        clip.save(update_fields=["file_path", "status"])
        logger.info("Clip %s gerado com sucesso: %s", clip_id, output_path)
        return True

    except Clip.DoesNotExist:
        logger.error("Clip %s não encontrado", clip_id)
        return False
    except Exception as e:
        logger.error("Erro ao gerar clip %s: %s", clip_id, e)
        try:
            clip = Clip.objects.get(id=clip_id)
            clip.status = Clip.Status.FAILED
            clip.save(update_fields=["status"])
        except Clip.DoesNotExist:
            pass
        raise


@shared_task(name="recordings.check_storage_quota")
def check_storage_quota_task() -> dict:
    """Task periódica que verifica o uso de storage de todos os tenants.

    Loga WARNING se uso > STORAGE_QUOTA_WARN_THRESHOLD (padrão 80%).
    Loga ERROR se uso > 95% ou acima da quota.

    Returns:
        Dicionário com resultado por tenant.
    """
    from apps.recordings.services import check_storage_quota
    from apps.users.models import Tenant
    from django.conf import settings

    warn_threshold = getattr(settings, "STORAGE_QUOTA_WARN_THRESHOLD", 0.8)

    results = {}
    for tenant in Tenant.objects.all():
        quota_info = check_storage_quota(tenant.id)
        results[tenant.id] = quota_info

        ratio = quota_info["usage_ratio"]
        used_gb = quota_info["used_bytes"] / 1024 ** 3
        quota_gb = quota_info["quota_bytes"] / 1024 ** 3

        if quota_info["over_quota"]:
            logger.error(
                "Tenant %s (%s) ACIMA DA QUOTA: %.1f GB / %.1f GB (%.0f%%)",
                tenant.id, tenant.name, used_gb, quota_gb, ratio * 100,
            )
        elif ratio >= 0.95:
            logger.error(
                "Tenant %s (%s) CRÍTICO: %.1f GB / %.1f GB (%.0f%%)",
                tenant.id, tenant.name, used_gb, quota_gb, ratio * 100,
            )
        elif ratio >= warn_threshold:
            logger.warning(
                "Tenant %s (%s) alto uso de storage: %.1f GB / %.1f GB (%.0f%%)",
                tenant.id, tenant.name, used_gb, quota_gb, ratio * 100,
            )

    return results


@shared_task(name="recordings.cleanup_task")
def cleanup_recordings_task() -> dict:
    """Task periódica para limpeza de gravações antigas.

    Returns:
        Dicionário com estatísticas de limpeza.
    """
    from apps.recordings.services import cleanup_old_recordings

    logger.info("Iniciando task de limpeza de gravações antigas...")
    stats = cleanup_old_recordings()
    logger.info("Limpeza concluída: %s", stats)
    return stats
