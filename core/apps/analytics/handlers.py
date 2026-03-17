"""Handlers de ingest por plugin — roteamento de eventos analíticos."""
import logging
import time
from typing import Any

from apps.analytics.models import DwellEvent, RegionOfInterest
from apps.cameras.models import Camera
from apps.events.models import Event
from apps.users.models import Tenant
from shared.pubsub import publish

logger = logging.getLogger(__name__)

_REALTIME_CHANNEL = "vms:realtime"

# Rate limit por (plugin, camera_id, roi_id) → último timestamp publicado
# Evita flood no SSE de plugins stateless que disparam a cada frame
_LAST_PUBLISHED: dict[tuple[str, int, int | None], float] = {}

# Intervalos mínimos entre eventos SSE (segundos) por plugin
_RATE_LIMITS: dict[str, float] = {
    "intrusion_detection": 10.0,   # máx 1 alerta de intrusão por ROI a cada 10s
    "people_count":        5.0,    # contagem de pessoas: a cada 5s
    "vehicle_count":       5.0,    # contagem de veículos: a cada 5s
    "line_crossing":       2.0,    # cruzamento: a cada 2s (cada cruzamento é único)
    "lpr_parking":         0.0,    # sem rate limit — cada placa é deduplicada no plugin
}


def _should_publish(plugin: str, camera_id: int, roi_id: int | None) -> bool:
    """Retorna True se passou tempo suficiente desde o último publish deste plugin/ROI."""
    min_interval = _RATE_LIMITS.get(plugin, 0.0)
    if min_interval == 0.0:
        return True
    key = (plugin, camera_id, roi_id)
    now = time.monotonic()
    if now - _LAST_PUBLISHED.get(key, 0.0) < min_interval:
        return False
    _LAST_PUBLISHED[key] = now
    return True


def handle_vehicle_dwell(
    payload: dict[str, Any],
    camera_id: int,
    tenant_id: int,
) -> None:
    """Processa evento de permanência veicular do plugin vehicle_dwell.

    Cria ou atualiza um DwellEvent no banco e publica no canal SSE.

    Args:
        payload: Campos específicos do plugin (track_id, entered_at, …).
        camera_id: ID da câmera de origem.
        tenant_id: ID do tenant de origem.
    """
    try:
        camera = Camera.objects.get(id=camera_id, tenant_id=tenant_id)
    except Camera.DoesNotExist:
        logger.error(
            "handle_vehicle_dwell: câmera %d não encontrada para tenant %d",
            camera_id,
            tenant_id,
        )
        return

    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        logger.error("handle_vehicle_dwell: tenant %d não encontrado", tenant_id)
        return

    track_id: int = payload["track_id"]
    entered_at = payload["entered_at"]
    exited_at = payload.get("exited_at")
    dwell_seconds: int | None = payload.get("dwell_seconds")
    frame_path: str = payload.get("frame_path", "")
    is_valid: bool | None = payload.get("is_valid")

    roi: RegionOfInterest | None = None
    if roi_id := payload.get("roi_id"):
        roi = RegionOfInterest.objects.filter(id=roi_id, camera=camera).first()

    try:
        event = DwellEvent.objects.get(
            camera=camera,
            tenant=tenant,
            track_id=track_id,
            exited_at__isnull=True,
        )
        # Veículo saiu — atualiza evento existente
        if exited_at:
            event.exited_at = exited_at
            event.dwell_seconds = dwell_seconds
            event.is_valid = is_valid
            event.save(update_fields=["exited_at", "dwell_seconds", "is_valid"])
            logger.info(
                "DwellEvent atualizado: track=%d câmera=%d dwell=%ss válido=%s",
                track_id,
                camera_id,
                dwell_seconds,
                is_valid,
            )
        event_id = event.id
    except DwellEvent.DoesNotExist:
        event = DwellEvent.objects.create(
            camera=camera,
            tenant=tenant,
            roi=roi,
            track_id=track_id,
            entered_at=entered_at,
            exited_at=exited_at,
            dwell_seconds=dwell_seconds,
            frame_path=frame_path,
            is_valid=is_valid,
        )
        event_id = event.id
        logger.info(
            "DwellEvent criado: track=%d câmera=%d",
            track_id,
            camera_id,
        )

    publish(_REALTIME_CHANNEL, {
        "type": "dwell_event",
        "tenant_id": tenant_id,
        "camera_id": camera_id,
        "track_id": track_id,
        "event_id": event_id,
        "is_valid": is_valid,
        "dwell_seconds": dwell_seconds,
    })


def handle_intrusion_detection(
    payload: dict[str, Any],
    camera_id: int,
    tenant_id: int,
) -> None:
    """Processa evento de intrusão do plugin intrusion_detection.

    Não persiste no banco — publica diretamente no canal SSE.
    Rate limiting de eventos repetidos é responsabilidade do frontend/consumidor.

    Args:
        payload: roi_id, roi_name, detection_count, detections, timestamp.
        camera_id: ID da câmera de origem.
        tenant_id: ID do tenant de origem.
    """
    roi_id = payload.get("roi_id")
    if not _should_publish("intrusion_detection", camera_id, roi_id):
        return
    logger.info(
        "Intrusão detectada: câmera=%d roi=%s count=%d",
        camera_id,
        payload.get("roi_name"),
        payload.get("detection_count", 0),
    )
    # Persiste no banco
    try:
        camera = Camera.objects.get(id=camera_id, tenant_id=tenant_id)
        Event.objects.create(
            event_type="intrusion.detected",
            camera=camera,
            tenant_id=tenant_id,
            payload={
                "roi_id": roi_id,
                "roi_name": payload.get("roi_name"),
                "detection_count": payload.get("detection_count", 0),
                "frame_path": payload.get("frame_path", ""),
            },
        )
    except Exception as exc:
        logger.error("handle_intrusion_detection: falha ao persistir: %s", exc)
    publish(_REALTIME_CHANNEL, {
        "type": "intrusion_detected",
        "tenant_id": tenant_id,
        "camera_id": camera_id,
        "roi_id": roi_id,
        "roi_name": payload.get("roi_name"),
        "detection_count": payload.get("detection_count", 0),
        "timestamp": payload.get("timestamp"),
    })


def handle_people_count(
    payload: dict[str, Any],
    camera_id: int,
    tenant_id: int,
) -> None:
    """Processa evento de contagem de pessoas do plugin people_count.

    Não persiste no banco — publica no canal SSE para atualização do dashboard.

    Args:
        payload: roi_id, roi_name, count, timestamp.
        camera_id: ID da câmera de origem.
        tenant_id: ID do tenant de origem.
    """
    roi_id = payload.get("roi_id")
    if not _should_publish("people_count", camera_id, roi_id):
        return
    logger.info(
        "Contagem pessoas: câmera=%d roi=%s count=%d",
        camera_id,
        payload.get("roi_name"),
        payload.get("count", 0),
    )
    try:
        camera = Camera.objects.get(id=camera_id, tenant_id=tenant_id)
        Event.objects.create(
            event_type="motion.detected",
            camera=camera,
            tenant_id=tenant_id,
            payload={
                "roi_id": roi_id,
                "roi_name": payload.get("roi_name"),
                "count": payload.get("count", 0),
                "frame_path": payload.get("frame_path", ""),
            },
        )
    except Exception as exc:
        logger.error("handle_people_count: falha ao persistir: %s", exc)
    publish(_REALTIME_CHANNEL, {
        "type": "people_count",
        "tenant_id": tenant_id,
        "camera_id": camera_id,
        "roi_id": payload.get("roi_id"),
        "roi_name": payload.get("roi_name"),
        "count": payload.get("count", 0),
        "timestamp": payload.get("timestamp"),
    })


def handle_vehicle_count(
    payload: dict[str, Any],
    camera_id: int,
    tenant_id: int,
) -> None:
    """Processa evento de contagem de veículos do plugin vehicle_count.

    Não persiste no banco — publica no canal SSE.

    Args:
        payload: roi_id, roi_name, count, by_class, timestamp.
        camera_id: ID da câmera de origem.
        tenant_id: ID do tenant de origem.
    """
    roi_id = payload.get("roi_id")
    if not _should_publish("vehicle_count", camera_id, roi_id):
        return
    logger.info(
        "Contagem veículos: câmera=%d roi=%s count=%d by_class=%s",
        camera_id,
        payload.get("roi_name"),
        payload.get("count", 0),
        payload.get("by_class", {}),
    )
    publish(_REALTIME_CHANNEL, {
        "type": "vehicle_count",
        "tenant_id": tenant_id,
        "camera_id": camera_id,
        "roi_id": payload.get("roi_id"),
        "roi_name": payload.get("roi_name"),
        "count": payload.get("count", 0),
        "by_class": payload.get("by_class", {}),
        "timestamp": payload.get("timestamp"),
    })


def handle_lpr_parking(
    payload: dict[str, Any],
    camera_id: int,
    tenant_id: int,
) -> None:
    """Processa leitura de placa do plugin lpr_parking.

    Não persiste no banco (sem ParkingSession por ora) — publica no canal SSE.
    Deduplicação já feita no plugin; aqui apenas repassa ao frontend.

    Args:
        payload: plate, roi_id, roi_name, timestamp.
        camera_id: ID da câmera de origem.
        tenant_id: ID do tenant de origem.
    """
    plate: str = payload.get("plate", "")
    logger.info(
        "LPR detectado: câmera=%d placa=%s roi=%s",
        camera_id,
        plate,
        payload.get("roi_name"),
    )
    publish(_REALTIME_CHANNEL, {
        "type": "lpr_detection",
        "tenant_id": tenant_id,
        "camera_id": camera_id,
        "plate": plate,
        "roi_id": payload.get("roi_id"),
        "roi_name": payload.get("roi_name"),
        "timestamp": payload.get("timestamp"),
    })


def handle_line_crossing(
    payload: dict[str, Any],
    camera_id: int,
    tenant_id: int,
) -> None:
    """Processa evento de cruzamento de linha do plugin line_crossing.

    Não persiste no banco — publica no canal SSE com direção (AB ou BA).

    Args:
        payload: roi_id, roi_name, track_id, direction, class, timestamp.
        camera_id: ID da câmera de origem.
        tenant_id: ID do tenant de origem.
    """
    direction = payload.get("direction", "")
    logger.info(
        "Cruzamento: câmera=%d roi=%s classe=%s direção=%s",
        camera_id,
        payload.get("roi_name"),
        payload.get("class"),
        direction,
    )
    publish(_REALTIME_CHANNEL, {
        "type":      "line_crossing",
        "tenant_id": tenant_id,
        "camera_id": camera_id,
        "roi_id":    payload.get("roi_id"),
        "roi_name":  payload.get("roi_name"),
        "track_id":  payload.get("track_id"),
        "direction": direction,
        "class":     payload.get("class"),
        "timestamp": payload.get("timestamp"),
    })


_FACE_MATCH_THRESHOLD = float(__import__('os').environ.get("FACE_MATCH_THRESHOLD", "0.50"))


def handle_face_recognition(
    payload: dict[str, Any],
    camera_id: int,
    tenant_id: int,
) -> None:
    """Processa detecção facial: matching contra FaceProfiles do tenant.

    Fluxo:
      1. Verifica tenant.facial_recognition_enabled (LGPD gate)
      2. Carrega todos os FaceProfiles do tenant com lgpd_consent=True
      3. Computa cosine similarity entre embedding recebido e cada perfil
      4. Se similarity >= FACE_MATCH_THRESHOLD → FaceDetectionEvent identificado
      5. Caso contrário → FaceDetectionEvent is_unknown=True
      6. Publica no canal SSE

    Args:
        payload: embedding, roi_id, roi_name, det_score, frame_path, timestamp.
        camera_id: ID da câmera.
        tenant_id: ID do tenant.
    """
    import numpy as np
    from apps.analytics.models import FaceDetectionEvent, FaceProfile, RegionOfInterest
    from apps.cameras.models import Camera
    from apps.users.models import Tenant

    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        logger.error("handle_face_recognition: tenant %d não encontrado", tenant_id)
        return

    # ── LGPD gate ─────────────────────────────────────────────────────────────
    if not tenant.facial_recognition_enabled:
        logger.warning(
            "handle_face_recognition: tenant %d sem facial_recognition_enabled — ignorado",
            tenant_id,
        )
        return

    try:
        camera = Camera.objects.get(id=camera_id, tenant=tenant)
    except Camera.DoesNotExist:
        logger.error("handle_face_recognition: câmera %d não encontrada", camera_id)
        return

    embedding_list: list[float] | None = payload.get("embedding")
    if not embedding_list or len(embedding_list) != 512:
        logger.error("handle_face_recognition: embedding inválido ou ausente")
        return

    probe = np.array(embedding_list, dtype=np.float32)

    # ROI
    roi_id = payload.get("roi_id")
    roi = RegionOfInterest.objects.filter(id=roi_id, camera=camera).first() if roi_id else None

    # ── Matching ──────────────────────────────────────────────────────────────
    profiles = list(FaceProfile.objects.filter(tenant=tenant, lgpd_consent=True))
    best_profile = None
    best_sim = 0.0

    for profile in profiles:
        gallery = np.array(profile.embedding, dtype=np.float32)
        sim = float(np.dot(probe, gallery))  # já normalizados → dot = cosine sim
        if sim > best_sim:
            best_sim = sim
            best_profile = profile

    is_unknown = best_profile is None or best_sim < _FACE_MATCH_THRESHOLD

    event = FaceDetectionEvent.objects.create(
        camera=camera,
        tenant=tenant,
        roi=roi,
        face_profile=None if is_unknown else best_profile,
        confidence=round(best_sim, 4),
        is_unknown=is_unknown,
        frame_path=payload.get("frame_path", ""),
    )

    if is_unknown:
        logger.info(
            "Rosto DESCONHECIDO: câmera=%d best_sim=%.3f event=%d",
            camera_id, best_sim, event.id,
        )
        publish(_REALTIME_CHANNEL, {
            "type":         "face_unknown",
            "tenant_id":    tenant_id,
            "camera_id":    camera_id,
            "event_id":     event.id,
            "best_sim":     round(best_sim, 3),
            "roi_name":     payload.get("roi_name"),
            "frame_path":   payload.get("frame_path", ""),
            "timestamp":    payload.get("timestamp"),
        })
    else:
        logger.info(
            "Rosto RECONHECIDO: câmera=%d perfil='%s' sim=%.3f event=%d",
            camera_id, best_profile.name, best_sim, event.id,
        )
        publish(_REALTIME_CHANNEL, {
            "type":         "face_recognized",
            "tenant_id":    tenant_id,
            "camera_id":    camera_id,
            "event_id":     event.id,
            "profile_id":   best_profile.id,
            "profile_name": best_profile.name,
            "confidence":   round(best_sim, 3),
            "roi_name":     payload.get("roi_name"),
            "frame_path":   payload.get("frame_path", ""),
            "timestamp":    payload.get("timestamp"),
        })


# Mapa de plugin_name → handler function
PLUGIN_HANDLERS: dict[str, Any] = {
    "vehicle_dwell":       handle_vehicle_dwell,
    "intrusion_detection": handle_intrusion_detection,
    "people_count":        handle_people_count,
    "vehicle_count":       handle_vehicle_count,
    "lpr_parking":         handle_lpr_parking,
    "line_crossing":       handle_line_crossing,
    "face_recognition":    handle_face_recognition,
}


def dispatch_ingest(
    plugin: str,
    camera_id: int,
    tenant_id: int,
    payload: dict[str, Any],
) -> bool:
    """Roteia evento de ingest para o handler correto pelo nome do plugin.

    Args:
        plugin: Nome do plugin (ex: "vehicle_dwell").
        camera_id: ID da câmera.
        tenant_id: ID do tenant.
        payload: Campos específicos do evento.

    Returns:
        True se despachado com sucesso, False se plugin desconhecido.
    """
    handler = PLUGIN_HANDLERS.get(plugin)
    if not handler:
        logger.warning("dispatch_ingest: plugin desconhecido '%s'", plugin)
        return False

    handler(payload, camera_id, tenant_id)
    return True
