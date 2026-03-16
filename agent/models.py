"""Dataclasses de domínio do agent (sem ORM)."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CameraConfig:
    """Configuração de uma câmera recebida do backend.

    Attributes:
        id: ID interno da câmera no VMS.
        name: Nome descritivo.
        rtsp_url: URL RTSP da câmera na rede local.
        rtmp_push_url: URL RTMP completa para push no MediaMTX.
        enabled: Se a câmera deve estar ativa.
    """

    id: int
    name: str
    rtsp_url: str
    rtmp_push_url: str
    enabled: bool = True


@dataclass
class StreamProcess:
    """Estado de um processo ffmpeg gerenciando um stream.

    Attributes:
        camera_id: ID da câmera associada.
        camera_config: Configuração da câmera (para detectar mudanças).
        process: Subprocesso ffmpeg rodando.
        started_at: Quando o stream começou.
        restart_count: Quantas vezes foi reiniciado consecutivamente.
        last_error: Última mensagem de erro.
        backoff_until: Não reiniciar antes deste timestamp.
    """

    camera_id: int
    camera_config: CameraConfig
    process: subprocess.Popen | None = None
    started_at: datetime | None = None
    restart_count: int = 0
    last_error: str | None = None
    backoff_until: datetime | None = None

    @property
    def is_running(self) -> bool:
        """Verifica se o processo ffmpeg está rodando."""
        return self.process is not None and self.process.poll() is None

    @property
    def uptime_seconds(self) -> float:
        """Segundos desde que o stream iniciou."""
        if self.started_at is None:
            return 0.0
        return (datetime.now() - self.started_at).total_seconds()
