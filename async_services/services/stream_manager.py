"""Gerenciador de streams via MediaMTX API."""
import os
from typing import Any

import httpx

MEDIAMTX_API_URL = os.environ.get("MEDIAMTX_API_URL", "http://mediamtx:9997")


async def list_active_streams() -> list[dict[str, Any]]:
    """Lista streams ativos no MediaMTX.

    Returns:
        Lista de streams com path, source e status.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{MEDIAMTX_API_URL}/v3/paths/list",
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "path": item["name"],
            "source": item.get("source", {}).get("type", "unknown"),
            "ready": item.get("ready", False),
            "readers": len(item.get("readers", [])),
        }
        for item in data.get("items", [])
    ]


async def get_path_source(path: str) -> str | None:
    """Retorna a URL RTSP de origem de um path no MediaMTX.

    Args:
        path: Nome do path (ex: tenant-1/cam-3).

    Returns:
        URL RTSP de origem ou None se não encontrado.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{MEDIAMTX_API_URL}/v3/config/paths/get/{path}",
                timeout=5.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("source") or None
    except Exception:
        return None
