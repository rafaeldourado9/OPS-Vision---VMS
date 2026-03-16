"""Configuração do agent carregada de variáveis de ambiente."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    """Configuração completa do agent.

    Attributes:
        api_url: URL base da API do VMS (ex: https://cloud.example.com/api/v1).
        api_key: API key retornada ao criar o agent no dashboard.
        rtmp_base_url: URL base RTMP do MediaMTX (fallback; config do backend tem prioridade).
        poll_interval: Intervalo em segundos entre polls de configuração.
        heartbeat_interval: Intervalo em segundos entre heartbeats.
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR).
        request_timeout: Timeout em segundos para requests HTTP.
    """

    api_url: str
    api_key: str
    rtmp_base_url: str = "rtmp://localhost:1935"
    poll_interval: int = 30
    heartbeat_interval: int = 60
    log_level: str = "INFO"
    request_timeout: float = 10.0

    @classmethod
    def from_env(cls) -> AgentConfig:
        """Cria configuração a partir de variáveis de ambiente.

        Required:
            VMS_API_URL: URL base da API.
            VMS_API_KEY: API key do agent.

        Optional:
            VMS_RTMP_URL: URL base RTMP (default: rtmp://localhost:1935).
            VMS_POLL_INTERVAL: Intervalo de poll em segundos (default: 30).
            VMS_HEARTBEAT_INTERVAL: Intervalo de heartbeat (default: 60).
            VMS_LOG_LEVEL: Nível de log (default: INFO).
            VMS_REQUEST_TIMEOUT: Timeout HTTP em segundos (default: 10).

        Returns:
            Instância de AgentConfig.

        Raises:
            ValueError: Se variáveis obrigatórias estiverem ausentes.
        """
        api_url = os.environ.get("VMS_API_URL")
        if not api_url:
            raise ValueError(
                "VMS_API_URL é obrigatório. "
                "Exemplo: https://cloud.example.com/api/v1"
            )

        api_key = os.environ.get("VMS_API_KEY")
        if not api_key:
            raise ValueError(
                "VMS_API_KEY é obrigatório. "
                "Obtenha a key ao criar um agent no dashboard."
            )

        return cls(
            api_url=api_url.rstrip("/"),
            api_key=api_key,
            rtmp_base_url=os.environ.get(
                "VMS_RTMP_URL", "rtmp://localhost:1935"
            ).rstrip("/"),
            poll_interval=int(os.environ.get("VMS_POLL_INTERVAL", "30")),
            heartbeat_interval=int(
                os.environ.get("VMS_HEARTBEAT_INTERVAL", "60")
            ),
            log_level=os.environ.get("VMS_LOG_LEVEL", "INFO").upper(),
            request_timeout=float(
                os.environ.get("VMS_REQUEST_TIMEOUT", "10")
            ),
        )
