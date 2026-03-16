"""Normalização de payloads ALPR de fabricantes específicos.

Converte payloads de Hikvision e Intelbras para o formato
interno ``ALPRDetectionInput``. Novos fabricantes podem ser
adicionados registrando uma função normalizer no registry
sem modificar a lógica de processamento principal.

Uso::

    from apps.events.normalizers import normalize_alpr_payload

    detection = normalize_alpr_payload("hikvision", camera_id=5, raw_payload={...})
"""
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from apps.events.services import ALPRDetectionInput


class UnsupportedManufacturerError(Exception):
    """Fabricante não suportado para normalização ALPR."""


# Registry: manufacturer_name → normalizer function
_normalizers: dict[str, Callable[[int, dict[str, Any]], ALPRDetectionInput]] = {}


def register_normalizer(
    manufacturer: str,
    fn: Callable[[int, dict[str, Any]], ALPRDetectionInput],
) -> None:
    """Registra um normalizer para um fabricante.

    Args:
        manufacturer: Nome do fabricante (lowercase).
        fn: Função que recebe (camera_id, raw_payload) e retorna ALPRDetectionInput.
    """
    _normalizers[manufacturer.lower()] = fn


def normalize_alpr_payload(
    manufacturer: str,
    camera_id: int,
    raw_payload: dict[str, Any],
) -> ALPRDetectionInput:
    """Normaliza payload ALPR de fabricante específico.

    Args:
        manufacturer: Nome do fabricante (case-insensitive).
        camera_id: ID interno da câmera no VMS.
        raw_payload: Payload bruto recebido do dispositivo.

    Returns:
        Dados normalizados para processamento.

    Raises:
        UnsupportedManufacturerError: Fabricante não registrado.
    """
    key = manufacturer.lower()
    normalizer = _normalizers.get(key)

    if normalizer is None:
        raise UnsupportedManufacturerError(
            f"Fabricante '{manufacturer}' não suportado. "
            f"Registrados: {list(_normalizers.keys())}"
        )

    return normalizer(camera_id, raw_payload)


# ── Hikvision ────────────────────────────────────────────


def _normalize_hikvision(
    camera_id: int,
    raw_payload: dict[str, Any],
) -> ALPRDetectionInput:
    """Normaliza payload ALPR da Hikvision.

    Formato esperado::

        {
            "EventNotificationAlert": {
                "channelID": "1",
                "dateTime": "2026-03-13T10:30:00-03:00",
                "ANPR": {
                    "licensePlate": "ABC1D23",
                    "confidenceLevel": 95,
                    "pictureURL": "http://..."
                }
            }
        }

    Args:
        camera_id: ID interno da câmera.
        raw_payload: Payload bruto Hikvision.

    Returns:
        Detecção normalizada.
    """
    alert = raw_payload["EventNotificationAlert"]
    anpr = alert["ANPR"]

    return ALPRDetectionInput(
        plate=anpr["licensePlate"],
        camera_id=camera_id,
        confidence=anpr["confidenceLevel"] / 100.0,
        timestamp=datetime.fromisoformat(alert["dateTime"]),
        image_url=anpr.get("pictureURL"),
    )


# ── Intelbras ────────────────────────────────────────────


def _normalize_intelbras(
    camera_id: int,
    raw_payload: dict[str, Any],
) -> ALPRDetectionInput:
    """Normaliza payload ALPR da Intelbras.

    Formato esperado::

        {
            "PlateResult": {
                "plate_number": "ABC-1D23",
                "confidence": 0.92,
                "capture_time": "2026-03-13 10:30:00",
                "channel": 1,
                "picture_url": "http://..."
            }
        }

    Args:
        camera_id: ID interno da câmera.
        raw_payload: Payload bruto Intelbras.

    Returns:
        Detecção normalizada.
    """
    result = raw_payload["PlateResult"]

    timestamp = datetime.strptime(
        result["capture_time"], "%Y-%m-%d %H:%M:%S",
    ).replace(tzinfo=UTC)

    return ALPRDetectionInput(
        plate=result["plate_number"],
        camera_id=camera_id,
        confidence=result["confidence"],
        timestamp=timestamp,
        image_url=result.get("picture_url"),
    )


# ── Genérico (fallback) ───────────────────────────────────


def _normalize_generic(
    camera_id: int,
    raw_payload: dict[str, Any],
) -> ALPRDetectionInput:
    """Normaliza payload ALPR genérico (JSON simples).

    Formato esperado::

        {
            "plate": "ABC1D23",
            "confidence": 0.92,
            "timestamp": "2026-03-13T10:30:00Z",
            "image_url": "http://..."    (opcional)
        }

    Args:
        camera_id: ID interno da câmera.
        raw_payload: Payload bruto JSON.

    Returns:
        Detecção normalizada.

    Raises:
        KeyError: Se ``plate`` ou ``confidence`` estiverem ausentes.
    """
    ts_raw = raw_payload.get("timestamp")
    if ts_raw:
        timestamp = datetime.fromisoformat(ts_raw)
    else:
        timestamp = datetime.now(tz=UTC)

    return ALPRDetectionInput(
        plate=raw_payload["plate"],
        camera_id=camera_id,
        confidence=float(raw_payload["confidence"]),
        timestamp=timestamp,
        image_url=raw_payload.get("image_url"),
    )


# ── Registro dos normalizers ─────────────────────────────

register_normalizer("hikvision", _normalize_hikvision)
register_normalizer("intelbras", _normalize_intelbras)
register_normalizer("generic", _normalize_generic)
