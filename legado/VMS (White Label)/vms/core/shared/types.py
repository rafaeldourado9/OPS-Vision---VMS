"""TypedDicts e tipos compartilhados do VMS."""
from typing import TypedDict


class CameraEventPayload(TypedDict):
    """Payload de evento de câmera."""

    camera_id: int
    tenant_id: int


class ALPREventPayload(TypedDict):
    """Payload de evento ALPR."""

    plate: str
    camera_id: int
    confidence: float
    timestamp: str
    image_url: str | None


class MediaMTXReadyPayload(TypedDict):
    """Payload do webhook on_ready do MediaMTX."""

    path: str
    source_type: str
    source_id: str


class MediaMTXReadPayload(TypedDict):
    """Payload do webhook on_read do MediaMTX."""

    path: str
    reader_type: str
    reader_id: str


class StreamInfo(TypedDict):
    """Informações de um stream ativo."""

    path: str
    source: str
    ready: bool
    readers: int
