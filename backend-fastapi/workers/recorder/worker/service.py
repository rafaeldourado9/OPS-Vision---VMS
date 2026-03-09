import asyncio
import os
import subprocess
import httpx
from datetime import datetime, timedelta
from pathlib import Path
import aio_pika
import json


RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
STORAGE_PATH = os.getenv('STORAGE_PATH', '/app/storage')
MEDIAMTX_URL = os.getenv('MEDIAMTX_URL', 'http://mediamtx:8888')
DJANGO_URL = os.getenv('DJANGO_INTERNAL_URL', 'http://django:8000')
SEGMENT_DURATION = 600  # 10 minutos


class RecorderWorker:
    def __init__(self):
        self.active_recordings = {}
        self.http_client = httpx.AsyncClient()

    async def start_recording(self, camera_id, tenant_id, stream_url):
        """Inicia gravação de uma câmera"""
        output_dir = Path(STORAGE_PATH) / 'recordings' / tenant_id / camera_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_pattern = str(output_dir / f'segment_%Y%m%d_%H%M%S.mp4')
        
        # FFmpeg command para gravar em segmentos de 10 minutos
        cmd = [
            'ffmpeg',
            '-i', stream_url,
            '-c', 'copy',
            '-f', 'segment',
            '-segment_time', str(SEGMENT_DURATION),
            '-segment_format', 'mp4',
            '-strftime', '1',
            '-reset_timestamps', '1',
            output_pattern
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        self.active_recordings[camera_id] = {
            'process': process,
            'tenant_id': tenant_id,
            'output_dir': output_dir
        }
        
        # Monitor para novos segmentos
        asyncio.create_task(self.monitor_segments(camera_id, tenant_id, output_dir))
        
        return process

    async def monitor_segments(self, camera_id, tenant_id, output_dir):
        """Monitora novos segmentos e registra no Django"""
        processed_files = set()
        
        while camera_id in self.active_recordings:
            for file_path in output_dir.glob('segment_*.mp4'):
                if file_path not in processed_files:
                    # Aguarda arquivo ser completamente escrito
                    await asyncio.sleep(5)
                    
                    # Extrai timestamps do nome do arquivo
                    filename = file_path.stem
                    timestamp_str = filename.replace('segment_', '')
                    start_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    end_time = start_time + timedelta(seconds=SEGMENT_DURATION)
                    
                    # Registra no Django
                    await self.register_segment(
                        camera_id=camera_id,
                        start_time=start_time.isoformat(),
                        end_time=end_time.isoformat(),
                        file_path=str(file_path),
                        file_size=file_path.stat().st_size
                    )
                    
                    processed_files.add(file_path)
            
            await asyncio.sleep(30)

    async def register_segment(self, camera_id, start_time, end_time, file_path, file_size):
        """Registra segmento no Django"""
        try:
            response = await self.http_client.post(
                f'{DJANGO_URL}/api/v1/internal/segments/',
                json={
                    'camera': camera_id,
                    'start_time': start_time,
                    'end_time': end_time,
                    'file_path': file_path,
                    'file_size': file_size
                }
            )
            response.raise_for_status()
        except Exception as e:
            print(f'Erro ao registrar segmento: {e}')

    async def stop_recording(self, camera_id):
        """Para gravação de uma câmera"""
        if camera_id in self.active_recordings:
            recording = self.active_recordings[camera_id]
            recording['process'].terminate()
            await recording['process'].wait()
            del self.active_recordings[camera_id]

    async def consume_queue(self):
        """Consome fila RabbitMQ"""
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()
        
        # Fila de start
        start_queue = await channel.declare_queue('recording.start', durable=True)
        stop_queue = await channel.declare_queue('recording.stop', durable=True)
        
        async with start_queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    data = json.loads(message.body)
                    camera_id = data['camera_id']
                    tenant_id = data['tenant_id']
                    stream_url = data['stream_url']
                    
                    await self.start_recording(camera_id, tenant_id, stream_url)

        async with stop_queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    data = json.loads(message.body)
                    camera_id = data['camera_id']
                    
                    await self.stop_recording(camera_id)


async def main():
    worker = RecorderWorker()
    await worker.consume_queue()


if __name__ == '__main__':
    asyncio.run(main())
