import asyncio
import json
import os
import time as _time
from pathlib import Path

import aio_pika
import cv2
import numpy as np
import redis.asyncio as aioredis
import torch
from ultralytics import YOLO
from prometheus_client import Counter, Histogram
from common.metrics import MetricsServer, REGISTRY, messages_consumed_total, messages_failed_total

RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
STORAGE_PATH = os.getenv('STORAGE_PATH', '/app/storage')
MODEL_PLATE_DETECTOR = os.getenv('MODEL_PLATE_DETECTOR', '/app/models/plate_detector.pt')
CONFIDENCE_LPR = float(os.getenv('CONFIDENCE_LPR', '0.5'))
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# ── Prometheus metrics ────────────────────────────────────────
lpr_frames_processed = Counter(
    'lpr_frames_processed_total', 'Total frames processed by LPR',
    registry=REGISTRY,
)
lpr_plates_detected = Counter(
    'lpr_plates_detected_total', 'Total plates detected',
    registry=REGISTRY,
)
lpr_plates_processed = Counter(
    'lpr_plates_processed_total', 'Total plate crops sent to OCR',
    registry=REGISTRY,
)
lpr_ocr_success = Counter(
    'lpr_ocr_success_total', 'Successful OCR reads',
    registry=REGISTRY,
)
lpr_processing_seconds = Histogram(
    'lpr_processing_seconds', 'LPR end-to-end processing time per frame',
    registry=REGISTRY,
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)
lpr_ocr_seconds = Histogram(
    'lpr_ocr_seconds', 'OCR processing time per plate',
    registry=REGISTRY,
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)


class LPRWorker:
    def __init__(self):
        print(f'[LPRWorker] Iniciando OCR e Detector (device={DEVICE})', flush=True)
        self.plate_model = YOLO(MODEL_PLATE_DETECTOR)
        self.plate_model.to(DEVICE)

        # T2.1.1 — PaddleOCR substitui EasyOCR
        from paddleocr import PaddleOCR
        import logging
        logging.getLogger('ppocr').setLevel(logging.WARNING)
        try:
            self.reader = PaddleOCR(lang='en')
            print('[LPRWorker] PaddleOCR iniciado', flush=True)
        except Exception as e:
            print(f'[LPRWorker] PaddleOCR fallback: {e}', flush=True)
            self.reader = PaddleOCR(lang='en')
        self._pub_connection = None
        self._pub_channel = None
        self._redis: aioredis.Redis | None = None
        print(f'[LPRWorker] Pronto — aguardando ai.frame.lpr', flush=True)

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(REDIS_URL, decode_responses=False)
        return self._redis

    async def _load_frame(self, frame_data: dict) -> np.ndarray | None:
        """Load frame from Redis (new), base64, or disk (legacy)."""
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

        if 'frame_b64' in frame_data:
            import base64
            buf = base64.b64decode(frame_data['frame_b64'])
            arr = np.frombuffer(buf, dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)

        path = frame_data.get('frame_path')
        if not path:
            return None

        # Fallback: disk with retry for race condition
        import time
        for _ in range(5):
            if os.path.exists(path):
                img = cv2.imread(path)
                if img is not None:
                    return img
            time.sleep(0.1)

        print(f'[LPRWorker] Frame not found: key={frame_key} path={path}')
        return None

    def _save_snapshot(self, image: np.ndarray, tenant_id: str, camera_id: str, plate: str) -> str:
        from datetime import datetime
        now = datetime.now()
        rel = Path('snapshots') / tenant_id / 'lpr' / now.strftime('%Y%m') / plate
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

    def _clean_plate_text(self, text: str) -> str:
        """Remove invalid chars (brazilian plates are ABC1234 or ABC1D23)"""
        import re
        text = text.upper()
        text = re.sub(r'[^A-Z0-9]', '', text)
        if len(text) < 7:
            return ''
        return text

    async def process_frame(self, frame_data: dict):
        t0 = _time.monotonic()
        camera_id = frame_data['camera_id']
        tenant_id = frame_data['tenant_id']
        rois = frame_data.get('rois', [])

        frame = await self._load_frame(frame_data)
        if frame is None:
            print(f'[LPRWorker] Frame nulo: camera={camera_id[:8]}', flush=True)
            return

        # Simple approach for LPR: we just run it on the whole frame for now,
        # or we could mask by ROI. For now, running over the frame.
        results = self.plate_model(frame, conf=CONFIDENCE_LPR, verbose=False, device=DEVICE)

        if not results or not len(results[0].boxes):
            lpr_frames_processed.inc()
            lpr_processing_seconds.observe(_time.monotonic() - t0)
            return

        boxes = results[0].boxes.xyxy.cpu().numpy()
        print(f'[LPRWorker] camera={camera_id[:8]} placas_detectadas={len(boxes)}', flush=True)
        lpr_plates_processed.inc(len(boxes))

        for box in boxes:
            x1, y1, x2, y2 = map(int, box)

            # Add padding to the plate crop
            h, w = frame.shape[:2]
            px1 = max(0, x1 - 10)
            py1 = max(0, y1 - 10)
            px2 = min(w, x2 + 10)
            py2 = min(h, y2 + 10)

            plate_crop = frame[py1:py2, px1:px2]
            if plate_crop.size == 0:
                continue

            # T2.1.2 — PaddleOCR: ocr() retorna [[bbox_points, [text, score]], ...]
            t_ocr = _time.monotonic()
            ocr_raw = await asyncio.get_event_loop().run_in_executor(None, self.reader.ocr, plate_crop)
            lpr_ocr_seconds.observe(_time.monotonic() - t_ocr)

            # ocr_raw é [[linha, ...]] (1 sub-lista por página); pode ser None ou [[None]] sem texto
            ocr_page = (ocr_raw or [[]])[0] or []
            for line in ocr_page:
                if line is None:
                    continue
                _bbox, (text, conf) = line
                clean_plate = self._clean_plate_text(text)
                if not clean_plate:
                    continue

                lpr_ocr_success.inc()
                lpr_plates_detected.inc()
                print(f'[LPRWorker] Placa detectada: {clean_plate} ({conf:.2f})', flush=True)

                snap_path = await asyncio.get_event_loop().run_in_executor(
                    None, self._save_snapshot, plate_crop, tenant_id, camera_id, clean_plate
                )

                channel = await self._get_pub_channel()

                for roi in rois:
                    msg = {
                        'camera_id': camera_id,
                        'tenant_id': tenant_id,
                        'roi_id': str(roi['id']),
                        'event_type': 'lpr',
                        'data': {
                            'plate': clean_plate,
                            'confidence': float(conf)
                        },
                        'snapshot_path': snap_path,
                        'detected_at': __import__('datetime').datetime.now().isoformat(),
                    }
                    await channel.default_exchange.publish(
                        aio_pika.Message(body=json.dumps(msg).encode()),
                        routing_key='ai.events',
                    )

        lpr_frames_processed.inc()
        lpr_processing_seconds.observe(_time.monotonic() - t0)

    async def consume(self):
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=2)
        queue = await channel.declare_queue('ai.frame.lpr', durable=True)
        
        async def on_message(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    payload = json.loads(message.body)
                    messages_consumed_total.labels(worker='lpr', queue='ai.frame.lpr').inc()
                    await self.process_frame(payload)
                except Exception as e:
                    messages_failed_total.labels(worker='lpr', queue='ai.frame.lpr').inc()
                    import traceback
                    print(f'[LPRWorker] Erro: {e}')
                    traceback.print_exc()

        await queue.consume(on_message)

        server = MetricsServer(port=9100, worker_name='lpr-worker')
        await server.start()

        await asyncio.Future()

async def main():
    await LPRWorker().consume()

if __name__ == '__main__':
    asyncio.run(main())
