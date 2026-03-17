"""Orchestrator — coordena captura de frames e workers de plugins."""
import asyncio
import concurrent.futures
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

import cv2
import numpy as np

from analytics.base import AnalyticsPlugin, FrameMetadata
from config.settings import settings
from core.django_client import get_rois, post_ingest
from core.mediamtx_connector import MediaMTXConnector, StreamInfo
from core.redis_bus import RedisBus

logger = logging.getLogger(__name__)


class StreamCapture:
    """Conexão RTSP persistente por stream — evita reconexão a cada frame.

    Mantém um cv2.VideoCapture aberto com buffer mínimo (1 frame) para
    garantir que o frame consumido seja sempre o mais recente do stream.
    Reconecta com backoff exponencial em caso de falha (2s → 4s → … → 30s).
    """

    _MAX_BACKOFF = 30.0

    def __init__(self, rtsp_url: str) -> None:
        self._url = rtsp_url
        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.Lock()
        self._fail_count: int = 0
        self._next_retry: float = 0.0  # monotonic clock

    def read_frame(self) -> np.ndarray | None:
        """Lê um frame da conexão persistente. Thread-safe."""
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                if time.monotonic() < self._next_retry:
                    return None  # Ainda em backoff — não tenta reconectar
                self._open()
            if self._cap is None:
                return None
            ret, frame = self._cap.read()
            if not ret:
                logger.warning("StreamCapture: leitura falhou em %s — reconectando", self._url)
                self._release()
                self._schedule_retry()
                return None
            self._fail_count = 0
            self._next_retry = 0.0
            return frame

    def release(self) -> None:
        """Libera a conexão RTSP."""
        with self._lock:
            self._release()

    def _open(self) -> None:
        """Abre conexão RTSP com buffer mínimo para garantir frames recentes."""
        cap = cv2.VideoCapture(self._url)
        if not cap.isOpened():
            cap.release()
            self._schedule_retry()
            return
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap = cap
        self._fail_count = 0
        self._next_retry = 0.0
        logger.info("StreamCapture: conectado a %s", self._url)

    def _schedule_retry(self) -> None:
        """Agenda próxima tentativa com backoff exponencial."""
        self._fail_count += 1
        backoff = min(2.0 ** min(self._fail_count, 5), self._MAX_BACKOFF)
        self._next_retry = time.monotonic() + backoff

    def _release(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None


class Orchestrator:
    """Orquestra captura de frames, distribuição via Redis e processamento por plugins."""

    def __init__(
        self,
        connector: MediaMTXConnector,
        bus: RedisBus,
        plugins: dict[str, AnalyticsPlugin],
    ) -> None:
        self._connector = connector
        self._bus = bus
        self._plugins = plugins
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._captures: dict[str, StreamCapture] = {}
        # Executor dedicado para operações CPU-bound (inferência + captura de frame)
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=settings.FRAME_EXECUTOR_WORKERS,
            thread_name_prefix="analytics-worker",
        )

    async def start(self) -> None:
        """Descobre streams, lança tasks de captura e workers."""
        logger.info("Orchestrator iniciando")
        await self._connector.discover_streams()
        self._running = True

        # Task de redescoberta periódica
        self._tasks.append(asyncio.create_task(self._rediscovery_loop()))

        # Tasks de captura por stream
        for stream in self._connector.active_streams.values():
            self._start_capture(stream)

        # Workers por plugin
        for plugin_name in self._plugins:
            for worker_id in range(settings.WORKERS_PER_PLUGIN):
                self._tasks.append(
                    asyncio.create_task(self._worker(plugin_name, worker_id))
                )

        logger.info(
            "Orchestrator em execução: %d streams, %d plugins, %d workers/plugin, executor=%d threads",
            len(self._connector.active_streams),
            len(self._plugins),
            settings.WORKERS_PER_PLUGIN,
            settings.FRAME_EXECUTOR_WORKERS,
        )

    async def stop(self) -> None:
        """Cancela todas as tasks e libera conexões."""
        logger.info("Orchestrator encerrando")
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        for cap in self._captures.values():
            cap.release()
        self._captures.clear()
        self._executor.shutdown(wait=False)

    async def status(self) -> dict[str, Any]:
        """Retorna status operacional para health check."""
        queue_sizes = {
            name: await self._bus.queue_size(name) for name in self._plugins
        }
        return {
            "running": self._running,
            "active_streams": len(self._connector.active_streams),
            "plugins": list(self._plugins.keys()),
            "queue_sizes": queue_sizes,
        }

    # ── Tasks privadas ────────────────────────────────────────────────────────

    def _start_capture(self, stream: StreamInfo) -> None:
        """Cria StreamCapture e task de captura para um novo stream."""
        if stream.path_name not in self._captures:
            self._captures[stream.path_name] = StreamCapture(stream.rtsp_url)
        self._tasks.append(asyncio.create_task(self._capture_loop(stream)))

    async def _rediscovery_loop(self) -> None:
        """Reexamina MediaMTX a cada 30s e inicia tasks para novos streams."""
        while self._running:
            try:
                await asyncio.sleep(30)
                old = set(self._connector.active_streams.keys())
                await self._connector.discover_streams()
                new = set(self._connector.active_streams.keys())
                for path in new - old:
                    stream = self._connector.active_streams[path]
                    self._start_capture(stream)
                    logger.info("Novo stream detectado, captura iniciada: %s", path)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("_rediscovery_loop: %s", exc)

    async def _capture_loop(self, stream: StreamInfo) -> None:
        """Captura frames de um stream via conexão persistente e distribui para plugins."""
        interval = 1.0 / settings.FPS
        loop = asyncio.get_event_loop()
        capture = self._captures[stream.path_name]

        while self._running:
            try:
                frame: np.ndarray | None = await loop.run_in_executor(
                    self._executor, capture.read_frame
                )
                if frame is None:
                    await asyncio.sleep(interval)
                    continue

                metadata = {
                    "camera_id": stream.camera_id,
                    "tenant_id": stream.tenant_id,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "stream_url": stream.rtsp_url,
                }

                for plugin_name in self._plugins:
                    queue_depth = await self._bus.queue_size(plugin_name)
                    if queue_depth >= settings.MAX_QUEUE_DEPTH:
                        logger.warning(
                            "Fila %s cheia (%d frames) — frame da câmera %d descartado",
                            plugin_name, queue_depth, stream.camera_id,
                        )
                        continue
                    await self._bus.publish_frame(plugin_name, frame, metadata)

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("_capture_loop [%s]: %s", stream.path_name, exc)
                await asyncio.sleep(interval)

    async def _worker(self, plugin_name: str, worker_id: int) -> None:
        """Consome frames da fila e chama plugin.process_frame."""
        plugin = self._plugins[plugin_name]
        logger.info("Worker %s#%d iniciado", plugin_name, worker_id)

        while self._running:
            try:
                item = await self._bus.consume_frame(plugin_name, timeout=1)
                if item is None:
                    continue

                frame, raw_meta = item
                camera_id: int = raw_meta["camera_id"]
                tenant_id: int = raw_meta["tenant_id"]
                ts = datetime.fromisoformat(raw_meta["timestamp"])
                stream_url: str = raw_meta["stream_url"]

                metadata = FrameMetadata(
                    camera_id=camera_id,
                    tenant_id=tenant_id,
                    timestamp=ts,
                    stream_url=stream_url,
                )

                # Busca ROIs filtradas pelo roi_type do plugin
                all_rois = await get_rois(camera_id)
                rois = [r for r in all_rois if r.ia_type == plugin.roi_type]

                results = await plugin.process_frame(frame, metadata, rois)
                for result in results:
                    await post_ingest(result)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Worker %s#%d: %s", plugin_name, worker_id, exc)
                await asyncio.sleep(0.1)
