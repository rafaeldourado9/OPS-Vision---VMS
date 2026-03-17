"""MediaMTX Connector — descobre streams ativos via API REST do MediaMTX."""
import logging
import re
from dataclasses import dataclass

import aiohttp

from config.settings import settings

logger = logging.getLogger(__name__)

# Padrão de path gerado pelo VMS: tenant-{tenant_id}/cam-{camera_id}
_PATH_RE = re.compile(r"^tenant-(\d+)/cam-(\d+)$")


@dataclass
class StreamInfo:
    """Stream ativo descoberto no MediaMTX."""

    path_name: str
    camera_id: int
    tenant_id: int
    rtsp_url: str


class MediaMTXConnector:
    """Conecta em uma instância MediaMTX e lista streams ativos."""

    def __init__(self) -> None:
        self._api_url = settings.MEDIAMTX_URL
        self._rtsp_base = settings.MEDIAMTX_RTSP_BASE_URL
        self._user = settings.MEDIAMTX_API_USER
        self._password = settings.MEDIAMTX_API_PASSWORD
        self.active_streams: dict[str, StreamInfo] = {}

    async def discover_streams(self) -> dict[str, StreamInfo]:
        """Busca streams prontos via /v3/paths/list e devolve mapa path→StreamInfo.

        Somente inclui paths cujo nome siga o padrão ``tenant-{x}/cam-{y}``.
        """
        try:
            auth = (
                aiohttp.BasicAuth(self._user, self._password)
                if self._user
                else None
            )
            async with aiohttp.ClientSession(auth=auth) as session:
                async with session.get(
                    f"{self._api_url}/v3/paths/list",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status != 200:
                        logger.error(
                            "MediaMTX /v3/paths/list retornou %d", resp.status
                        )
                        return {}
                    data = await resp.json()
        except Exception as exc:
            logger.error("Erro ao contactar MediaMTX: %s", exc)
            return {}

        streams: dict[str, StreamInfo] = {}
        for item in data.get("items", []):
            path_name: str = item.get("name", "")
            if not item.get("ready", False):
                continue
            m = _PATH_RE.match(path_name)
            if not m:
                continue
            tenant_id = int(m.group(1))
            camera_id = int(m.group(2))
            rtsp_url = f"{self._rtsp_base}/{path_name}"
            streams[path_name] = StreamInfo(
                path_name=path_name,
                camera_id=camera_id,
                tenant_id=tenant_id,
                rtsp_url=rtsp_url,
            )

        logger.info("%d streams ativos encontrados no MediaMTX", len(streams))
        self.active_streams = streams
        return streams
