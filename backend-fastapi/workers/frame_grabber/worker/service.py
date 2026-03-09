import asyncio
import os
import cv2
from pathlib import Path
import aio_pika
import json
from datetime import datetime


RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
STORAGE_PATH = os.getenv('STORAGE_PATH', '/app/storage')
MEDIAMTX_URL = os.getenv('MEDIAMTX_URL', 'http://mediamtx:8888')


class FrameGrabberWorker:
    def __init__(self):
        self.active_cameras = {}

    async def start_grabbing(self, camera_id, tenant_id, stream_url, rois):
        """Inicia captura de frames de uma câmera"""
        if camera_id in self.active_cameras:
            return
        
        self.active_cameras[camera_id] = {
            'tenant_id': tenant_id,
            'stream_url': stream_url,
            'rois': rois,
            'running': True
        }
        
        asyncio.create_task(self.grab_frames(camera_id))

    async def grab_frames(self, camera_id):
        """Captura 1 frame por segundo e publica na fila ai.frame"""
        camera_data = self.active_cameras[camera_id]
        stream_url = camera_data['stream_url']
        
        # Conecta ao stream HLS
        cap = cv2.VideoCapture(stream_url)
        
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()
        queue = await channel.declare_queue('ai.frame', durable=True)
        
        while camera_data['running']:
            ret, frame = cap.read()
            
            if ret:
                # Salva frame temporário
                frame_dir = Path(STORAGE_PATH) / 'frames' / camera_data['tenant_id']
                frame_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                frame_path = frame_dir / f'{camera_id}_{timestamp}.jpg'
                cv2.imwrite(str(frame_path), frame)
                
                # Publica na fila ai.frame
                message = {
                    'camera_id': camera_id,
                    'tenant_id': camera_data['tenant_id'],
                    'frame_path': str(frame_path),
                    'rois': camera_data['rois']
                }
                
                await channel.default_exchange.publish(
                    aio_pika.Message(body=json.dumps(message).encode()),
                    routing_key='ai.frame'
                )
            
            await asyncio.sleep(1)  # 1 frame por segundo
        
        cap.release()
        await connection.close()

    async def stop_grabbing(self, camera_id):
        """Para captura de frames"""
        if camera_id in self.active_cameras:
            self.active_cameras[camera_id]['running'] = False
            del self.active_cameras[camera_id]

    async def consume_roi_updated(self):
        """Consome fila roi.updated para atualizar ROIs"""
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()
        queue = await channel.declare_queue('roi.updated', durable=True)
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    data = json.loads(message.body)
                    camera_id = data['camera_id']
                    roi_list = data['roi_list']
                    
                    if camera_id in self.active_cameras:
                        self.active_cameras[camera_id]['rois'] = roi_list


async def main():
    worker = FrameGrabberWorker()
    await worker.consume_roi_updated()


if __name__ == '__main__':
    asyncio.run(main())
