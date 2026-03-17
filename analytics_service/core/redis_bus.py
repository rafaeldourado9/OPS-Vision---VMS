"""Redis Bus — transporte de frames entre captura e workers de plugins."""
import json
import logging
import pickle
from typing import Any

import numpy as np
import redis.asyncio as aioredis

from config.settings import settings

logger = logging.getLogger(__name__)


class RedisBus:
    """Barramento de frames via listas Redis (producer/consumer)."""

    def __init__(self) -> None:
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Abre conexão com o Redis."""
        self._client = await aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
        )
        logger.info("RedisBus conectado")

    async def disconnect(self) -> None:
        """Fecha conexão com o Redis."""
        if self._client:
            await self._client.aclose()
            logger.info("RedisBus desconectado")

    async def publish_frame(
        self,
        plugin_name: str,
        frame: np.ndarray,
        metadata: dict[str, Any],
    ) -> None:
        """Enfileira frame para um plugin específico.

        Args:
            plugin_name: Nome do plugin destino (ex: "vehicle_dwell").
            frame: Frame BGR como numpy array.
            metadata: Dicionário com camera_id, tenant_id, timestamp, stream_url.
        """
        try:
            payload = pickle.dumps({"frame": frame, "metadata": metadata})
            queue = f"analytics:frames:{plugin_name}"
            await self._client.lpush(queue, payload)
        except Exception as exc:
            logger.error("Erro ao publicar frame para plugin %s: %s", plugin_name, exc)

    async def consume_frame(
        self,
        plugin_name: str,
        timeout: int = 1,
    ) -> tuple[np.ndarray, dict[str, Any]] | None:
        """Consome frame da fila de um plugin (bloqueante com timeout).

        Args:
            plugin_name: Nome do plugin.
            timeout: Segundos para aguardar (0 = sem timeout).

        Returns:
            Tupla (frame, metadata) ou None se timeout.
        """
        try:
            queue = f"analytics:frames:{plugin_name}"
            result = await self._client.brpop(queue, timeout=timeout)
            if not result:
                return None
            _, raw = result
            data = pickle.loads(raw)
            return data["frame"], data["metadata"]
        except Exception as exc:
            logger.error("Erro ao consumir frame do plugin %s: %s", plugin_name, exc)
            return None

    async def queue_size(self, plugin_name: str) -> int:
        """Retorna tamanho da fila de um plugin."""
        try:
            return await self._client.llen(f"analytics:frames:{plugin_name}")
        except Exception:
            return 0
