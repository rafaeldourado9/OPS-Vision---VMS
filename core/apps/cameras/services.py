"""Services de domínio para câmeras."""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

import jwt
from django.conf import settings
from django.db import transaction

from shared.cache import set_camera_status
from shared.event_bus import publish_event
from shared.mediamtx_client import MediaMTXClient
from shared import pubsub

from .models import Camera


class CameraOfflineError(Exception):
    """Câmera está offline."""


class StreamTokenInvalidError(Exception):
    """Token de stream inválido ou adulterado."""


class StreamTokenExpiredError(Exception):
    """Token de stream expirado."""


@dataclass(frozen=True)
class CameraCreateInput:
    """Dados para criar uma câmera."""
    name: str
    location: str
    rtsp_url: str
    manufacturer: str
    retention_days: int
    tenant_id: int
    agent_id: int | None = None


@dataclass(frozen=True)
class CameraUpdateInput:
    """Dados para atualizar uma câmera."""
    name: str | None = None
    location: str | None = None
    rtsp_url: str | None = None
    manufacturer: str | None = None
    retention_days: int | None = None


def create_camera(data: CameraCreateInput) -> Camera:
    """Cria uma câmera e registra o stream no MediaMTX.

    Args:
        data: Dados validados para criação.

    Returns:
        Câmera criada.

    Raises:
        MediaMTXError: Falha ao registrar stream.
    """
    with transaction.atomic():
        camera = Camera.objects.create(
            name=data.name,
            location=data.location,
            rtsp_url=data.rtsp_url,
            manufacturer=data.manufacturer,
            retention_days=data.retention_days,
            tenant_id=data.tenant_id,
            agent_id=data.agent_id,
        )

        client = MediaMTXClient()
        if data.agent_id:
            # Agent mode: aceita RTMP push do agent local
            client.add_path(name=_build_path_name(camera))
        else:
            # Pull mode: MediaMTX puxa RTSP diretamente
            client.add_path(
                name=_build_path_name(camera),
                source=data.rtsp_url,
            )

    publish_event("camera.created", {
        "camera_id": camera.id,
        "tenant_id": data.tenant_id,
        "name": data.name,
        "location": data.location,
    })

    return camera


def update_camera(camera_id: int, data: CameraUpdateInput) -> Camera:
    """Atualiza uma câmera.

    Args:
        camera_id: ID da câmera.
        data: Dados para atualização.

    Returns:
        Câmera atualizada.

    Raises:
        Camera.DoesNotExist: Câmera não encontrada.
        MediaMTXError: Falha ao atualizar path.
    """
    camera = Camera.objects.get(id=camera_id)
    original_rtsp = camera.rtsp_url
    changed_fields = []

    with transaction.atomic():
        if data.name is not None:
            camera.name = data.name
            changed_fields.append("name")

        if data.location is not None:
            camera.location = data.location
            changed_fields.append("location")

        if data.rtsp_url is not None:
            camera.rtsp_url = data.rtsp_url
            changed_fields.append("rtsp_url")

        if data.manufacturer is not None:
            camera.manufacturer = data.manufacturer
            changed_fields.append("manufacturer")

        if data.retention_days is not None:
            camera.retention_days = data.retention_days
            changed_fields.append("retention_days")

        camera.save()

        if data.rtsp_url is not None and data.rtsp_url != original_rtsp:
            client = MediaMTXClient()
            client.edit_path(
                name=_build_path_name(camera),
                source=data.rtsp_url,
            )

    publish_event("camera.updated", {
        "camera_id": camera.id,
        "tenant_id": camera.tenant_id,
        "changed_fields": changed_fields,
    })

    return camera


def delete_camera(camera_id: int) -> None:
    """Deleta uma câmera e remove o path do MediaMTX.

    Args:
        camera_id: ID da câmera.

    Raises:
        Camera.DoesNotExist: Câmera não encontrada.
        MediaMTXError: Falha ao remover path.
    """
    camera = Camera.objects.get(id=camera_id)
    camera_id_saved = camera.id
    tenant_id_saved = camera.tenant_id

    # Remove path do MediaMTX (best-effort — não impede a deleção)
    try:
        client = MediaMTXClient()
        client.remove_path(name=_build_path_name(camera))
    except Exception:
        logger.warning(
            "Falha ao remover path do MediaMTX para camera %d, continuando deleção.",
            camera_id,
        )

    camera.delete()

    publish_event("camera.deleted", {
        "camera_id": camera_id_saved,
        "tenant_id": tenant_id_saved,
    })


def get_camera_stream_url(camera_id: int) -> str:
    """Retorna a URL de streaming da câmera.

    Args:
        camera_id: ID da câmera.

    Returns:
        URL de streaming (WebRTC/HLS).

    Raises:
        Camera.DoesNotExist: Câmera não encontrada.
        CameraOfflineError: Câmera está offline.
    """
    camera = Camera.objects.get(id=camera_id)

    if not camera.is_online:
        raise CameraOfflineError(
            f"Camera {camera_id} is offline"
        )

    path = _build_path_name(camera)
    return f"{settings.MEDIAMTX_STREAM_BASE_URL}/{path}"


def generate_stream_token(camera_id: int, tenant_id: int) -> str:
    """Gera um JWT de acesso temporário para um stream de câmera.

    O token é assinado com SECRET_KEY e contém camera_id, tenant_id e expiração.
    MediaMTX valida este token via authHTTPAddress antes de servir o stream.

    Args:
        camera_id: ID da câmera.
        tenant_id: ID do tenant.

    Returns:
        JWT assinado como string.
    """
    ttl = getattr(settings, "STREAM_TOKEN_TTL_SECONDS", 1800)
    payload = {
        "camera_id": camera_id,
        "tenant_id": tenant_id,
        "type": "stream",
        "exp": datetime.now(tz=timezone.utc) + timedelta(seconds=ttl),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def verify_stream_token(token: str) -> dict:
    """Verifica e decodifica um stream token.

    Args:
        token: JWT gerado por generate_stream_token.

    Returns:
        Dicionário com camera_id e tenant_id.

    Raises:
        StreamTokenExpiredError: Token expirado.
        StreamTokenInvalidError: Token inválido ou adulterado.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise StreamTokenExpiredError("Stream token expirado.") from e
    except (jwt.InvalidTokenError, Exception) as e:
        raise StreamTokenInvalidError("Stream token inválido.") from e

    if payload.get("type") != "stream":
        raise StreamTokenInvalidError("Tipo de token inválido.")

    return {"camera_id": payload["camera_id"], "tenant_id": payload["tenant_id"]}


def set_camera_online(camera_id: int, is_online: bool) -> None:
    """Atualiza o status online/offline da câmera no banco e no cache.

    Publica evento ``camera_status`` no canal ``vms:realtime`` via Redis pub/sub
    para que clientes SSE recebam a atualização em tempo real.

    Args:
        camera_id: ID da câmera.
        is_online: True se online, False se offline.

    Raises:
        Camera.DoesNotExist: Câmera não encontrada.
    """
    camera = Camera.objects.get(id=camera_id)
    camera.is_online = is_online
    camera.save(update_fields=["is_online"])
    set_camera_status(camera_id, is_online)
    pubsub.publish(
        "vms:realtime",
        {
            "type": "camera_status",
            "camera_id": camera_id,
            "is_online": is_online,
            "tenant_id": camera.tenant_id,
        },
    )


def generate_rtmp_push_url(camera_id: int, tenant_id: int) -> dict[str, str]:
    """Gera credenciais RTMP push para configurar uma câmera.

    Fluxo:
    - MediaMTX recebe a conexão RTMP e chama POST /streaming/auth/
    - FastAPI valida o token HMAC-SHA256(path, MEDIAMTX_PUBLISH_SECRET)
    - Token aprovado → stream aceito

    Returns:
        Dict com rtmp_url, stream_key, username, password e full_url.
    """
    import hashlib
    import hmac as _hmac

    camera = Camera.objects.get(id=camera_id)
    rtmp_base = settings.MEDIAMTX_RTMP_URL
    path = f"tenant-{camera.tenant_id}/cam-{camera.id}"
    secret = getattr(settings, "MEDIAMTX_PUBLISH_SECRET", "")

    token = _hmac.new(
        secret.encode(), path.encode(), hashlib.sha256
    ).hexdigest()[:24]

    username = f"cam-{camera.id}"

    return {
        "rtmp_url": rtmp_base,
        "stream_key": path,
        "username": username,
        "password": token,
        # URL com credenciais embutidas (compatível com FFmpeg, OBS, etc.)
        "full_url": f"rtmp://{username}:{token}@{rtmp_base.removeprefix('rtmp://')}/{path}",
    }


def _build_path_name(camera: Camera) -> str:
    """Gera nome único do path no MediaMTX.
    
    Args:
        camera: Instância da câmera.
        
    Returns:
        Nome do path no formato tenant-{tenant_id}/cam-{camera_id}.
    """
    return f"tenant-{camera.tenant_id}/cam-{camera.id}"
