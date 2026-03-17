"""Facial Recognition worker — InsightFace buffalo_l, isolated GPU worker."""
import asyncio
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import aio_pika
import cv2
import numpy as np
import redis
import redis.asyncio as aioredis
from prometheus_client import Counter, Gauge, Histogram
from common.metrics import MetricsServer, REGISTRY, messages_consumed_total, messages_failed_total

RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
STORAGE_PATH = os.getenv('STORAGE_PATH', '/app/storage')
FACIAL_DEDUP_TTL = int(os.getenv('FACIAL_DEDUP_TTL', '45'))
SIMILARITY_THRESHOLD = float(os.getenv('FACIAL_SIMILARITY_THRESHOLD', '0.5'))
DJANGO_URL = os.getenv('DJANGO_INTERNAL_URL', 'http://django:8000')
INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', 'changeme')
MAX_CONCURRENT = int(os.getenv('MAX_CONCURRENT_FRAMES', '2'))
UNKNOWN_EVENTS_ENABLED = os.getenv('FACIAL_UNKNOWN_EVENTS', 'false').lower() == 'true'


# ── Prometheus metrics ────────────────────────────────────────
facial_frames_processed = Counter(
    'facial_frames_processed_total', 'Frames processed by facial worker',
    registry=REGISTRY,
)
facial_faces_detected = Counter(
    'facial_faces_detected_total', 'Total faces detected',
    registry=REGISTRY,
)
facial_matches = Counter(
    'facial_matches_total', 'Successful face matches',
    ['match_type'], registry=REGISTRY,
)
facial_inference_seconds = Histogram(
    'facial_inference_seconds', 'Facial inference duration per frame',
    registry=REGISTRY,
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
facial_model_loaded = Gauge(
    'facial_model_loaded', 'Whether InsightFace model is loaded (1=yes)',
    registry=REGISTRY,
)


class FacialWorker:
    def __init__(self):
        self.redis = redis.from_url(REDIS_URL)
        self._redis_async: aioredis.Redis | None = None
        self._analyzer = None
        self._analyzer_ready = asyncio.Event()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self._pub_connection = None
        self._pub_channel = None
        self._loop = None  # set in consume()
        print('[FacialWorker] Iniciando InsightFace (pode levar ~30s)...', flush=True)

    async def _get_redis_async(self) -> aioredis.Redis:
        if self._redis_async is None:
            self._redis_async = aioredis.from_url(REDIS_URL, decode_responses=False)
        return self._redis_async

    def _load_analyzer_sync(self):
        """Load InsightFace model in background thread."""
        try:
            from worker.analyzers.facial import FacialAnalyzer
            self._analyzer = FacialAnalyzer()
            facial_model_loaded.set(1)
            print('[FacialWorker] InsightFace carregado!', flush=True)
            # Schedule persons reload on the event loop
            if self._loop:
                asyncio.run_coroutine_threadsafe(self._reload_persons(), self._loop)
            self._loop.call_soon_threadsafe(self._analyzer_ready.set)
        except Exception as e:
            import traceback
            print(f'[FacialWorker] ERRO ao carregar InsightFace: {e}', flush=True)
            traceback.print_exc()

    async def _reload_persons(self):
        """Fetch known persons from Django and load their embeddings."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f'{DJANGO_URL}/api/v1/internal/persons/',
                    headers={'X-Internal-Key': INTERNAL_API_KEY},
                    timeout=30.0,
                )
                resp.raise_for_status()
                persons = resp.json()
                if self._analyzer:
                    # Run embedding extraction in executor (CPU-bound)
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self._analyzer.load_persons, persons)
                print(f'[FacialWorker] {len(persons)} pessoas carregadas do Django', flush=True)
        except Exception as e:
            print(f'[FacialWorker] Erro ao buscar persons: {e}', flush=True)

    async def _load_frame_async(self, frame_data: dict) -> np.ndarray | None:
        """Load frame from Redis (new), base64, or disk (legacy)."""
        # Try Redis first
        frame_key = frame_data.get('frame_key')
        if frame_key:
            try:
                r = await self._get_redis_async()
                data = await r.get(frame_key)
                if data is not None:
                    arr = np.frombuffer(data, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        return frame
            except Exception:
                pass

        if 'frame_b64' in frame_data:
            import base64
            buf = base64.b64decode(frame_data['frame_b64'])
            return cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR)

        path = frame_data.get('frame_path')
        if not path:
            return None

        # Fallback: disk with retry
        loop = asyncio.get_event_loop()
        def _read():
            for _ in range(5):
                if os.path.exists(path):
                    img = cv2.imread(path)
                    if img is not None:
                        return img
                time.sleep(0.1)
            return None
        return await loop.run_in_executor(None, _read)

    def _save_snapshot(self, image: np.ndarray, tenant_id: str, camera_id: str,
                       event_type: str, subfolder: str = '') -> str:
        now = datetime.now()
        rel = Path('snapshots') / tenant_id / event_type / now.strftime('%Y%m')
        if subfolder:
            rel = rel / subfolder
        abs_dir = Path(STORAGE_PATH) / rel
        abs_dir.mkdir(parents=True, exist_ok=True)
        name = f'{now.strftime("%Y%m%d_%H%M%S_%f")}.jpg'
        cv2.imwrite(str(abs_dir / name), image)
        return str(rel / name)

    async def _get_pub_channel(self):
        if self._pub_connection is None or self._pub_connection.is_closed:
            self._pub_connection = await aio_pika.connect_robust(RABBITMQ_URL)
            self._pub_channel = await self._pub_connection.channel()
            await self._pub_channel.declare_queue('ai.events', durable=True)
        return self._pub_channel

    async def publish_event(self, camera_id, tenant_id, roi_id, event_type, event_data, snapshot_path):
        channel = await self._get_pub_channel()
        msg = {
            'camera_id': camera_id,
            'tenant_id': tenant_id,
            'roi_id': roi_id,
            'event_type': event_type,
            'data': event_data,
            'snapshot_path': snapshot_path,
            'detected_at': datetime.now().isoformat(),
        }
        await channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(msg).encode()),
            routing_key='ai.events',
        )
        print(f'[FacialWorker] >>> {event_type} camera={camera_id[:8]} '
              f'person={event_data.get("person_name", "?")} '
              f'sim={event_data.get("similarity", 0):.3f}', flush=True)

    async def process_frame(self, frame_data: dict):
        if not self._analyzer:
            return  # Still loading

        camera_id = frame_data['camera_id']
        tenant_id = frame_data['tenant_id']

        frame = await self._load_frame_async(frame_data)
        if frame is None:
            return

        t0 = time.monotonic()

        for roi in frame_data.get('rois', []):
            roi_id = str(roi['id'])
            polygon = roi.get('polygon', [])
            polygon_px = []
            if polygon:
                h, w = frame.shape[:2]
                polygon_px = [[int(x * w), int(y * h)] for x, y in polygon]

            # Run face detection + recognition in executor (GPU-bound)
            events = await loop.run_in_executor(
                None, self._analyzer.analyze, frame, polygon_px, tenant_id
            )

            for evt in events:
                event_type = evt['event_type']

                # Skip unknown face events unless explicitly enabled
                if event_type == 'facial_unknown' and not UNKNOWN_EVENTS_ENABLED:
                    continue

                person_id = evt['event_data'].get('person_id', 'unknown')
                dedup_key = f'dedup:facial:{camera_id}:{roi_id}:{person_id}'
                if self.redis.exists(dedup_key):
                    continue
                self.redis.setex(dedup_key, FACIAL_DEDUP_TTL, '1')

                face_img = evt.get('face_image', frame)
                snap = await loop.run_in_executor(
                    None,
                    self._save_snapshot,
                    face_img, tenant_id, camera_id, event_type, str(person_id),
                )
                facial_faces_detected.inc()
                facial_matches.labels(match_type=event_type).inc()
                await self.publish_event(
                    camera_id=camera_id, tenant_id=tenant_id, roi_id=roi_id,
                    event_type=event_type,
                    event_data=evt['event_data'],
                    snapshot_path=snap,
                )

        facial_frames_processed.inc()
        facial_inference_seconds.observe(time.monotonic() - t0)
        elapsed = (time.monotonic() - t0) * 1000
        n_rois = len(frame_data.get('rois', []))
        print(f'[FacialWorker] Frame processado em {elapsed:.0f}ms ({n_rois} ROIs) '
              f'camera={camera_id[:8]}', flush=True)

    async def consume(self):
        self._loop = asyncio.get_event_loop()

        # Start model loading in background thread
        threading.Thread(target=self._load_analyzer_sync, daemon=True).start()

        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=MAX_CONCURRENT)
        queue = await channel.declare_queue('ai.frame.facial', durable=True)
        print('[FacialWorker] Aguardando ai.frame.facial...', flush=True)

        async def on_message(message: aio_pika.IncomingMessage):
            async with message.process():
                async with self._semaphore:
                    try:
                        frame_data = json.loads(message.body)
                        messages_consumed_total.labels(worker='facial', queue='ai.frame.facial').inc()
                        await self.process_frame(frame_data)
                    except Exception as e:
                        messages_failed_total.labels(worker='facial', queue='ai.frame.facial').inc()
                        import traceback
                        print(f'[FacialWorker] Erro: {e}')
                        traceback.print_exc()

        # Listen for persons.updated to reload embeddings in real-time
        persons_queue = await channel.declare_queue('persons.updated', durable=True)

        async def on_persons_updated(message: aio_pika.IncomingMessage):
            async with message.process():
                print('[FacialWorker] persons.updated — recarregando embeddings', flush=True)
                await self._reload_persons()

        await queue.consume(on_message)
        await persons_queue.consume(on_persons_updated)

        # Wait for model to be ready before processing
        print('[FacialWorker] Aguardando modelo carregar...', flush=True)
        await self._analyzer_ready.wait()
        print('[FacialWorker] Modelo pronto! Processando frames.', flush=True)

        server = MetricsServer(port=9100, worker_name='facial-worker')
        await server.start()

        await asyncio.Future()


async def main():
    worker = FacialWorker()
    await worker.consume()


if __name__ == '__main__':
    asyncio.run(main())
