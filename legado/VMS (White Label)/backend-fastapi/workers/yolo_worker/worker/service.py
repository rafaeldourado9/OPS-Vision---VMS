"""YOLO Worker — Object detection + ByteTrack tracking.

Consumes frames from ai.frame.yolo queue (new) and legacy ai.frame queue.
Runs single YOLO inference per frame, then dispatches detections to
per-analytic queues (ai.detect.{type}).

Supports loading frames from Redis (frame_key) or disk (frame_path).
"""

import asyncio
import json
import os

import time as _time

import aio_pika
import cv2
import numpy as np
import redis.asyncio as aioredis
import torch
import supervision as sv
from ultralytics import YOLO
from prometheus_client import Counter, Gauge, Histogram
from common.metrics import MetricsServer, REGISTRY, messages_consumed_total, messages_failed_total

RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
MODEL_PATH = os.getenv('YOLO_MODEL', 'yolov8n.pt')
CONFIDENCE = float(os.getenv('CONFIDENCE_GENERAL', '0.4'))
MAX_CONCURRENT = int(os.getenv('MAX_CONCURRENT_FRAMES', '4'))
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# COCO class IDs
_COCO_NAMES = {
    0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle',
    5: 'bus', 7: 'truck', 15: 'cat', 16: 'dog',
    24: 'backpack', 26: 'handbag', 28: 'suitcase',
}
VEHICLE_IDS = {2, 3, 5, 7}
PERSON_IDS = {0}
OBJECT_IDS = {24, 26, 28}
ALL_IDS = VEHICLE_IDS | PERSON_IDS | OBJECT_IDS

# ia_type → which class IDs to pass down
_TYPE_CLASS_MAP = {
    'object_detection': ALL_IDS,
    'crowd': PERSON_IDS,
    'intrusion': PERSON_IDS | VEHICLE_IDS,
    'loitering': PERSON_IDS,
    'abandoned_object': OBJECT_IDS | PERSON_IDS,
    'queue': PERSON_IDS,
    'heatmap': PERSON_IDS,
    'line_crossing': ALL_IDS,
    'human_traffic': PERSON_IDS,
    'vehicle_traffic': VEHICLE_IDS,
}

# Per-analytic output queues
_TYPE_QUEUE = {t: f'ai.detect.{t}' for t in _TYPE_CLASS_MAP}


def _expand_roi_types(rois: list) -> list:
    """Expand multi-analytic ROIs (ia_types) into one entry per ia_type."""
    result = []
    for roi in rois:
        types = roi.get('ia_types') or []
        if types:
            for t in types:
                result.append({**roi, 'ia_type': t})
        else:
            result.append(roi)
    return result

# Input queues (consume both new and legacy)
# ── Prometheus metrics ────────────────────────────────────────
yolo_frames_processed = Counter(
    'yolo_frames_processed_total', 'Total frames processed by YOLO',
    registry=REGISTRY,
)
yolo_inference_seconds = Histogram(
    'yolo_inference_seconds', 'YOLO inference duration',
    registry=REGISTRY,
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)
yolo_detections_total = Counter(
    'yolo_detections_total', 'Total objects detected',
    ['class_name'], registry=REGISTRY,
)
yolo_dispatched_total = Counter(
    'yolo_dispatched_total', 'Messages dispatched to analytic queues',
    ['queue'], registry=REGISTRY,
)

_INPUT_QUEUE_NEW = 'ai.frame.yolo'
_INPUT_QUEUE_LEGACY = 'ai.frame'


class YoloWorker:
    def __init__(self):
        print(f'[YoloWorker] Iniciando (device={DEVICE})', flush=True)
        self.model = YOLO(MODEL_PATH)
        self.model.to(DEVICE)
        self._trackers: dict[str, sv.ByteTrack] = {}
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self._pub_connection = None
        self._pub_channel = None
        self._redis: aioredis.Redis | None = None
        self._metrics_server = None
        print(f'[YoloWorker] Pronto — device={DEVICE}', flush=True)

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(REDIS_URL, decode_responses=False)
        return self._redis

    def _get_tracker(self, camera_id: str) -> sv.ByteTrack:
        if camera_id not in self._trackers:
            self._trackers[camera_id] = sv.ByteTrack(
                frame_rate=3, lost_track_buffer=30, minimum_consecutive_frames=1,
            )
        return self._trackers[camera_id]

    async def _get_pub_channel(self):
        if self._pub_connection is None or self._pub_connection.is_closed:
            self._pub_connection = await aio_pika.connect_robust(RABBITMQ_URL)
            self._pub_channel = await self._pub_connection.channel()
        return self._pub_channel

    async def _ensure_queues(self, channel):
        await channel.declare_queue(_INPUT_QUEUE_NEW, durable=True)
        await channel.declare_queue(_INPUT_QUEUE_LEGACY, durable=True)
        for q in _TYPE_QUEUE.values():
            await channel.declare_queue(q, durable=True)

    async def _load_frame(self, frame_data: dict) -> np.ndarray | None:
        """Load frame from Redis (new) or disk (legacy)."""
        # Try Redis first
        frame_key = frame_data.get('frame_key')
        if frame_key:
            try:
                r = await self._get_redis()
                data = await r.get(frame_key)
                if data is not None:
                    arr = np.frombuffer(data, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        return frame
            except Exception:
                pass

        # Try base64 (inline)
        if 'frame_b64' in frame_data:
            import base64
            buf = base64.b64decode(frame_data['frame_b64'])
            arr = np.frombuffer(buf, dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)

        # Fallback: disk path
        path = frame_data.get('frame_path')
        if path:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, cv2.imread, path)

        return None

    def _serialize_detections(self, detections: sv.Detections, width: int, height: int) -> list:
        result = []
        for i in range(len(detections)):
            x1, y1, x2, y2 = detections.xyxy[i].tolist()
            result.append({
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                'rx1': x1 / width, 'ry1': y1 / height,
                'rx2': x2 / width, 'ry2': y2 / height,
                'class_id': int(detections.class_id[i]),
                'class_name': _COCO_NAMES.get(int(detections.class_id[i]), f'cls_{int(detections.class_id[i])}'),
                'confidence': float(detections.confidence[i]),
                'tracker_id': int(detections.tracker_id[i]) if detections.tracker_id is not None and detections.tracker_id[i] is not None else None,
            })
        return result

    async def process_frame(self, frame_data: dict):
        camera_id = frame_data['camera_id']
        tenant_id = frame_data['tenant_id']
        rois = frame_data.get('rois', [])
        if not rois:
            return

        # Expand multi-analytic ROIs (ia_types=[...]) into one per ia_type
        rois = _expand_roi_types(rois)

        # Determine needed COCO classes across all ROIs
        needed_classes = set()
        for roi in rois:
            ia_type = roi.get('ia_type', '')
            needed_classes |= _TYPE_CLASS_MAP.get(ia_type, set())
        if not needed_classes:
            return

        frame = await self._load_frame(frame_data)
        if frame is None:
            src = frame_data.get('frame_key') or frame_data.get('frame_path', '?')
            print(f'[YoloWorker] Frame not found: {src}', flush=True)
            return

        height, width = frame.shape[:2]

        # Single YOLO inference
        t0 = _time.monotonic()
        results = self.model(
            frame,
            conf=CONFIDENCE,
            classes=list(needed_classes),
            verbose=False,
            device=DEVICE,
        )
        yolo_inference_seconds.observe(_time.monotonic() - t0)
        detections = sv.Detections.from_ultralytics(results[0])

        yolo_frames_processed.inc()
        for i in range(len(detections)):
            cls_name = _COCO_NAMES.get(int(detections.class_id[i]), 'unknown')
            yolo_detections_total.labels(class_name=cls_name).inc()

        # ByteTrack for stable IDs
        tracker = self._get_tracker(camera_id)
        detections = tracker.update_with_detections(detections)

        dets_serialized = self._serialize_detections(detections, width, height)

        channel = await self._get_pub_channel()

        # Base payload — forward frame references for snapshot copying downstream
        base_payload = {
            'camera_id': camera_id,
            'tenant_id': tenant_id,
            'frame_key': frame_data.get('frame_key'),
            'frame_path': frame_data.get('frame_path', ''),
            'frame_width': width,
            'frame_height': height,
            'detections': dets_serialized,
        }

        # Group ROIs by ia_type and dispatch to per-analytic queues
        rois_by_type: dict[str, list] = {}
        for roi in rois:
            ia_type = roi.get('ia_type', '')
            if ia_type in _TYPE_QUEUE:
                rois_by_type.setdefault(ia_type, []).append(roi)

        for ia_type, type_rois in rois_by_type.items():
            queue_name = _TYPE_QUEUE[ia_type]
            payload = {**base_payload, 'rois': type_rois}
            await channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps(payload).encode()),
                routing_key=queue_name,
            )
            yolo_dispatched_total.labels(queue=queue_name).inc()

    async def consume(self):
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=MAX_CONCURRENT)
        await self._ensure_queues(channel)

        # Consume from both new and legacy queues
        queue_new = await channel.declare_queue(_INPUT_QUEUE_NEW, durable=True)
        queue_legacy = await channel.declare_queue(_INPUT_QUEUE_LEGACY, durable=True)

        print(f'[YoloWorker] Aguardando frames em {_INPUT_QUEUE_NEW} + {_INPUT_QUEUE_LEGACY} '
              f'(device={DEVICE}, concurrency={MAX_CONCURRENT})...', flush=True)

        async def on_message(message: aio_pika.IncomingMessage):
            async with message.process():
                async with self._semaphore:
                    try:
                        frame_data = json.loads(message.body)
                        messages_consumed_total.labels(worker='yolo', queue=message.routing_key or 'unknown').inc()
                        await self.process_frame(frame_data)
                    except Exception as e:
                        messages_failed_total.labels(worker='yolo', queue=message.routing_key or 'unknown').inc()
                        import traceback
                        print(f'[YoloWorker] Erro: {e}')
                        traceback.print_exc()

        await queue_new.consume(on_message)
        await queue_legacy.consume(on_message)

        # Start metrics server
        self._metrics_server = MetricsServer(port=9100, worker_name='yolo-worker')
        self._metrics_server.register_health_check('rabbitmq', lambda: self._pub_connection is not None and not self._pub_connection.is_closed)
        await self._metrics_server.start()

        await asyncio.Future()


async def main():
    worker = YoloWorker()
    await worker.consume()


if __name__ == '__main__':
    asyncio.run(main())
