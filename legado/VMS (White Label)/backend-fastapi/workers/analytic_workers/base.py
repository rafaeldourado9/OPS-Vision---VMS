"""Base class for all per-analytic CPU workers."""
import asyncio
import json
import os
import time
import time as _time
from abc import ABC, abstractmethod

import aio_pika
import redis
from prometheus_client import Counter, Histogram
from common.metrics import MetricsServer, REGISTRY, messages_consumed_total, messages_failed_total, events_published_total

RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
STORAGE_PATH = os.getenv('STORAGE_PATH', '/app/storage')
DEDUP_TTL = int(os.getenv('DEDUP_TTL_SECONDS', '30'))


# ── Prometheus metrics ────────────────────────────────────────
analytic_events_processed = Counter(
    'analytic_events_processed_total', 'Events processed by analytic worker',
    ['worker'], registry=REGISTRY,
)
analytic_processing_seconds = Histogram(
    'analytic_processing_seconds', 'Analytic processing time',
    ['worker'], registry=REGISTRY,
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)


class BaseAnalyticWorker(ABC):
    """
    Base class shared by all per-analytic workers.

    Subclasses must implement:
      - queue_name: str   → the RabbitMQ queue to consume
      - process(payload)  → analytic logic; call self.publish_event() to emit events
    """

    queue_name: str  # e.g. 'ai.detect.crowd'

    def __init__(self):
        self.redis = redis.from_url(REDIS_URL)
        self._pub_connection = None
        self._pub_channel = None
        # Stateful workers can store per-camera-per-roi state here
        self._state: dict = {}
        self._now = time.time

    # ──────────────────────────────────────────────────────────
    # Redis dedup helpers
    # ──────────────────────────────────────────────────────────

    def is_dedup(self, key: str, ttl: int | None = None) -> bool:
        """Return True if key exists (event was already sent recently)."""
        return bool(self.redis.exists(key))

    def set_dedup(self, key: str, ttl: int | None = None):
        self.redis.setex(key, ttl or DEDUP_TTL, '1')

    # ──────────────────────────────────────────────────────────
    # Detection helpers
    # ──────────────────────────────────────────────────────────

    def filter_by_classes(self, detections: list, class_ids: set) -> list:
        return [d for d in detections if d['class_id'] in class_ids]

    def in_polygon(self, detections: list, polygon: list, width: int, height: int) -> list:
        """Return detections whose center is inside the normalized polygon."""
        if not polygon or not detections:
            return detections  # no polygon = full frame
        import cv2
        import numpy as np
        pts = np.array([[int(x * width), int(y * height)] for x, y in polygon], dtype=np.int32)
        result = []
        for d in detections:
            cx = int((d['x1'] + d['x2']) / 2)
            cy = int((d['y1'] + d['y2']) / 2)
            if cv2.pointPolygonTest(pts, (cx, cy), False) >= 0:
                result.append(d)
        return result

    # ──────────────────────────────────────────────────────────
    # Event publishing
    # ──────────────────────────────────────────────────────────

    async def _get_pub_channel(self):
        if self._pub_connection is None or self._pub_connection.is_closed:
            self._pub_connection = await aio_pika.connect_robust(RABBITMQ_URL)
            self._pub_channel = await self._pub_connection.channel()
            await self._pub_channel.declare_queue('ai.events', durable=True)
        return self._pub_channel

    async def publish_event(
        self,
        camera_id: str,
        tenant_id: str,
        roi_id: str,
        event_type: str,
        event_data: dict,
        frame_path: str = '',
    ):
        from datetime import datetime
        from pathlib import Path
        import shutil
        
        channel = await self._get_pub_channel()
        
        # Copia frame para snapshots/
        snapshot_path = ''
        if frame_path and Path(frame_path).exists():
            snapshot_dir = Path(STORAGE_PATH) / 'snapshots' / tenant_id
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            snapshot_filename = Path(frame_path).name
            snapshot_full_path = snapshot_dir / snapshot_filename
            shutil.copy2(frame_path, snapshot_full_path)
            # Caminho relativo para o banco
            snapshot_path = f'snapshots/{tenant_id}/{snapshot_filename}'
        
        message = {
            'camera_id': camera_id,
            'tenant_id': tenant_id,
            'roi_id': roi_id,
            'event_type': event_type,
            'data': event_data,
            'snapshot_path': snapshot_path,
            'detected_at': datetime.now().isoformat(),
        }
        await channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key='ai.events',
        )
        events_published_total.labels(worker=self.__class__.__name__, event_type=event_type).inc()
        print(f'[{self.__class__.__name__}] >>> {event_type} camera={camera_id[:8]} data={json.dumps(event_data)[:120]}', flush=True)

    # ──────────────────────────────────────────────────────────
    # Main loop
    # ──────────────────────────────────────────────────────────

    @abstractmethod
    async def process(self, payload: dict):
        """Analytic logic. Payload contains: camera_id, tenant_id, rois, detections, frame_path, frame_width, frame_height."""

    async def consume(self):
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=8)
        queue = await channel.declare_queue(self.queue_name, durable=True)
        worker_name = self.__class__.__name__
        print(f'[{worker_name}] Aguardando {self.queue_name}...', flush=True)

        async def on_message(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    payload = json.loads(message.body)
                    messages_consumed_total.labels(worker=worker_name, queue=self.queue_name).inc()
                    t0 = _time.monotonic()
                    await self.process(payload)
                    analytic_events_processed.labels(worker=worker_name).inc()
                    analytic_processing_seconds.labels(worker=worker_name).observe(_time.monotonic() - t0)
                except Exception as e:
                    messages_failed_total.labels(worker=worker_name, queue=self.queue_name).inc()
                    import traceback
                    print(f'[{worker_name}] Erro: {e}')
                    traceback.print_exc()

        await queue.consume(on_message)

        server = MetricsServer(port=9100, worker_name=worker_name)
        await server.start()

        await asyncio.Future()
