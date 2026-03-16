"""Client HTTP para a API do MediaMTX (v3)."""
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class MediaMTXError(Exception):
    """Erro de comunicação com MediaMTX."""


@dataclass
class MediaMTXPath:
    """Representação de um path no MediaMTX."""

    name: str
    source: str
    ready: bool = False


class MediaMTXClient:
    """Client HTTP para a API do MediaMTX (v3).

    Endpoints usados:
    - GET    /v3/paths/list            (paths ativos com status)
    - GET    /v3/config/paths/get/{n}  (configuração de um path)
    - POST   /v3/config/paths/add/{n}
    - PATCH  /v3/config/paths/patch/{n}
    - DELETE /v3/config/paths/delete/{n}
    """

    def __init__(self) -> None:
        self.base_url = getattr(
            settings, "MEDIAMTX_API_URL", "http://localhost:9997"
        )
        self.timeout = 10.0
        self.auth = (
            getattr(settings, "MEDIAMTX_API_USER", "mediamtx_api_user"),
            getattr(settings, "MEDIAMTX_API_PASSWORD", "GtV!sionMed1aMTX$2025"),
        )

    def list_paths(self) -> list[MediaMTXPath]:
        """Lista todos os paths ativos (com status de stream).

        Returns:
            Lista de paths com nome, source e status ready.
        """
        data = self._get("/v3/paths/list")
        return [
            MediaMTXPath(
                name=item["name"],
                source=item.get("source", {}).get("type", ""),
                ready=item.get("ready", False),
            )
            for item in data.get("items", [])
        ]

    def add_path(self, name: str, source: str = "publisher") -> None:
        """Adiciona um path de câmera.

        Args:
            name: Nome único do path (ex: tenant-1/cam-1).
            source: URL RTSP da câmera ou ``"publisher"`` para
                    aceitar RTMP push (default).

        Raises:
            MediaMTXError: Falha ao adicionar path.
        """
        self._post(f"/v3/config/paths/add/{name}", {"source": source})

    def edit_path(self, name: str, source: str) -> None:
        """Atualiza a source de um path.

        Args:
            name: Nome único do path.
            source: Nova URL RTSP da câmera.

        Raises:
            MediaMTXError: Falha ao atualizar path.
        """
        self._patch(f"/v3/config/paths/patch/{name}", {"source": source})

    def remove_path(self, name: str) -> None:
        """Remove um path de câmera.

        Args:
            name: Nome único do path.

        Raises:
            MediaMTXError: Falha ao remover path.
        """
        self._delete(f"/v3/config/paths/delete/{name}")

    def get_path(self, name: str) -> dict[str, Any]:
        """Obtém configuração de um path.

        Args:
            name: Nome do path.

        Returns:
            Configuração do path.

        Raises:
            MediaMTXError: Falha ao obter path.
        """
        return self._get(f"/v3/config/paths/get/{name}")

    # ── HTTP helpers ──────────────────────────────────────

    def _get(self, path: str) -> dict[str, Any]:
        """GET request com tratamento de erro."""
        try:
            resp = httpx.get(
                f"{self.base_url}{path}", timeout=self.timeout, auth=self.auth
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise MediaMTXError(f"GET {path} failed: {e}") from e

    def _post(self, path: str, data: dict[str, Any]) -> None:
        """POST request."""
        try:
            resp = httpx.post(
                f"{self.base_url}{path}", json=data, timeout=self.timeout, auth=self.auth
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise MediaMTXError(f"POST {path} failed: {e}") from e

    def _patch(self, path: str, data: dict[str, Any]) -> None:
        """PATCH request."""
        try:
            resp = httpx.patch(
                f"{self.base_url}{path}", json=data, timeout=self.timeout, auth=self.auth
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise MediaMTXError(f"PATCH {path} failed: {e}") from e

    def _delete(self, path: str) -> None:
        """DELETE request."""
        try:
            resp = httpx.delete(
                f"{self.base_url}{path}", timeout=self.timeout, auth=self.auth
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise MediaMTXError(f"DELETE {path} failed: {e}") from e
