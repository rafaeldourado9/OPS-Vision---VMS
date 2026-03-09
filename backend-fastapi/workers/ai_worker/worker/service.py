import asyncio
import os
import cv2
import numpy as np
from pathlib import Path
import aio_pika
import redis
import httpx
import json
from datetime import datetime


RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
MODEL_PLATE_DETECTOR = os.getenv('MODEL_PLATE_DETECTOR', '/app/models/plate_detector.pt')
MODEL_CHAR_RECOGNIZER = os.getenv('MODEL_CHAR_RECOGNIZER', '/app/models/char_recognizer.pt')
STORAGE_PATH = os.getenv('STORAGE_PATH', '/app/storage')
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.7'))
DEDUP_TTL_SECONDS = int(os.getenv('DEDUP_TTL_SECONDS', '30'))
DJANGO_URL = os.getenv('DJANGO_INTERNAL_URL', 'http://django:8000')


class AIWorker:
    def __init__(self):
        self.redis_client = redis.from_url(REDIS_URL)
        self.http_client = httpx.AsyncClient()
        
        # Carrega modelos YOLOv8 (simulado - na prática usaria ultralytics)
        # from ultralytics import YOLO
        # self.plate_detector = YOLO(MODEL_PLATE_DETECTOR)
        # self.char_recognizer = YOLO(MODEL_CHAR_RECOGNIZER)

    def point_in_polygon(self, point, polygon):
        """Ray casting para verificar se ponto está dentro do polígono"""
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside

    async def process_frame(self, frame_data):
        """Processa frame para detecção de placas"""
        camera_id = frame_data['camera_id']
        tenant_id = frame_data['tenant_id']
        frame_path = frame_data['frame_path']
        rois = frame_data['rois']
        
        # Carrega frame
        frame = cv2.imread(frame_path)
        if frame is None:
            return
        
        height, width = frame.shape[:2]
        
        for roi in rois:
            if roi['ia_type'] != 'lpr':
                continue
            
            # Converte polígono normalizado para pixels
            polygon_pixels = [[int(x * width), int(y * height)] for x, y in roi['polygon']]
            
            # Crop do ROI (bounding box)
            xs = [p[0] for p in polygon_pixels]
            ys = [p[1] for p in polygon_pixels]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            
            roi_crop = frame[y_min:y_max, x_min:x_max]
            
            # Inferência YOLOv8 (simulado)
            # results = self.plate_detector(roi_crop)
            # Simulação de detecção
            detected_plates = self.simulate_plate_detection(roi_crop)
            
            for plate_data in detected_plates:
                if plate_data['confidence'] < CONFIDENCE_THRESHOLD:
                    continue
                
                plate_string = plate_data['plate']
                
                # Dedup via Redis
                dedup_key = f'dedup:{camera_id}:{plate_string}'
                if self.redis_client.exists(dedup_key):
                    continue  # Evento duplicado
                
                self.redis_client.setex(dedup_key, DEDUP_TTL_SECONDS, '1')
                
                # Salva snapshot da placa
                snapshot_dir = Path(STORAGE_PATH) / 'snapshots' / tenant_id
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                snapshot_path = snapshot_dir / f'{camera_id}_{plate_string}_{timestamp}.jpg'
                cv2.imwrite(str(snapshot_path), plate_data['plate_image'])
                
                # Publica evento
                await self.publish_event(
                    camera_id=camera_id,
                    tenant_id=tenant_id,
                    roi_id=roi['id'],
                    event_type='lpr',
                    event_data={'plate': plate_string, 'confidence': plate_data['confidence']},
                    snapshot_path=str(snapshot_path)
                )

    def simulate_plate_detection(self, image):
        """Simula detecção de placas (substituir por YOLOv8 real)"""
        # Na prática: results = self.plate_detector(image)
        # Retorna lista de detecções simuladas
        return [
            {
                'plate': 'ABC1D23',
                'confidence': 0.85,
                'plate_image': image
            }
        ]

    async def publish_event(self, camera_id, tenant_id, roi_id, event_type, event_data, snapshot_path):
        """Publica evento na fila ai.events"""
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()
        
        message = {
            'camera_id': camera_id,
            'tenant_id': tenant_id,
            'roi_id': roi_id,
            'event_type': event_type,
            'data': event_data,
            'snapshot_path': snapshot_path,
            'detected_at': datetime.now().isoformat()
        }
        
        await channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key='ai.events'
        )
        
        await connection.close()

    async def consume_frames(self):
        """Consome fila ai.frame"""
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()
        queue = await channel.declare_queue('ai.frame', durable=True)
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    frame_data = json.loads(message.body)
                    await self.process_frame(frame_data)


async def main():
    worker = AIWorker()
    await worker.consume_frames()


if __name__ == '__main__':
    asyncio.run(main())
