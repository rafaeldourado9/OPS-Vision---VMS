"""Cliente HTTP para comunicação com a API do VMS."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import AgentConfig
from .models import CameraConfig

logger = logging.getLogger(__name__)

# Versão do agent — atualizar a cada release
AGENT_VERSION = "0.1.0"


class CloudClient:
    """Cliente para consumir a API Django do VMS.

    Usa ``Authorization: Agent <api_key>`` conforme o backend espera.

    Args:
        config: Configuração do agent.
    """

    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._base_url = config.api_url
        self._headers = {"Authorization": f"Agent {config.api_key}"}
        self._timeout = config.request_timeout

    async def get_config(self) -> list[CameraConfig]:
        """Obtém a configuração desejada do backend.

        Chama ``GET /agents/me/config/`` e parseia a resposta em
        lista de ``CameraConfig``.

        Returns:
            Lista de configurações de câmeras.
            Lista vazia se houve erro na comunicação.
        """
        url = f"{self._base_url}/agents/me/config/"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url,
                    headers=self._headers,
                    timeout=self._timeout,
                )

            if resp.status_code == 401:
                logger.error(
                    "Autenticação falhou (401). Verifique VMS_API_KEY."
                )
                raise AuthenticationError("API key inválida ou agent revogado.")

            resp.raise_for_status()
            data = resp.json()

            cameras = [
                CameraConfig(
                    id=cam["id"],
                    name=cam["name"],
                    rtsp_url=cam["rtsp_url"],
                    rtmp_push_url=cam["rtmp_push_url"],
                    enabled=cam.get("enabled", True),
                )
                for cam in data.get("cameras", [])
            ]

            logger.debug(
                "Config recebida: %d câmeras ativas",
                len([c for c in cameras if c.enabled]),
            )
            return cameras

        except AuthenticationError:
            raise
        except httpx.TimeoutException:
            logger.warning(
                "Timeout ao obter config de %s (timeout=%.1fs)",
                url,
                self._timeout,
            )
            return []
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Erro HTTP %d ao obter config: %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return []
        except Exception:
            logger.exception("Erro inesperado ao obter config")
            return []

    async def send_heartbeat(
        self,
        uptime_seconds: int,
        cameras_status: dict[str, Any],
    ) -> bool:
        """Envia heartbeat para o backend.

        Chama ``POST /agents/me/heartbeat/`` com versão, uptime e
        status das câmeras.

        Args:
            uptime_seconds: Tempo de atividade do agent em segundos.
            cameras_status: Status de cada câmera (camera_id → info).

        Returns:
            True se o heartbeat foi aceito.
        """
        url = f"{self._base_url}/agents/me/heartbeat/"
        payload = {
            "version": AGENT_VERSION,
            "uptime_seconds": uptime_seconds,
            "cameras": cameras_status,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers=self._headers,
                    timeout=self._timeout,
                )

            resp.raise_for_status()
            logger.debug("Heartbeat enviado com sucesso")
            return True

        except httpx.TimeoutException:
            logger.warning("Timeout ao enviar heartbeat")
            return False
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Erro HTTP %d ao enviar heartbeat: %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return False
        except Exception:
            logger.exception("Erro inesperado ao enviar heartbeat")
            return False


class AuthenticationError(Exception):
    """API key inválida ou agent revogado."""
