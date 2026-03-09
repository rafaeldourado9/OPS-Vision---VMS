import asyncio
import os
import subprocess
from pathlib import Path

import aio_pika
import httpx
import json


RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
STORAGE_PATH = os.getenv('STORAGE_PATH', '/app/storage')
DJANGO_URL = os.getenv('DJANGO_INTERNAL_URL', 'http://django:8000')


class ClipBuilderWorker:
    """Constrói clipes de vídeo a partir de segmentos gravados."""

    def __init__(self):
        self.http_client = httpx.AsyncClient()

    async def build_clip(self, clip_data: dict):
        """
        Recebe dados do clipe e usa FFmpeg para concatenar
        segmentos no intervalo [start_time, end_time].
        """
        clip_id = clip_data['clip_id']
        camera_id = clip_data['camera_id']
        start_time = clip_data['start_time']
        end_time = clip_data['end_time']

        # Atualiza status para 'processing'
        await self._update_clip_status(clip_id, 'processing')

        try:
            # Busca segmentos disponíveis via Django
            response = await self.http_client.get(
                f'{DJANGO_URL}/api/v1/cameras/{camera_id}/segments/',
                params={'start': start_time, 'end': end_time}
            )
            response.raise_for_status()
            segments = response.json()

            if not segments:
                await self._update_clip_status(clip_id, 'failed')
                return

            # Cria lista de arquivos para FFmpeg concat
            output_dir = Path(STORAGE_PATH) / 'clips'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f'{clip_id}.mp4'

            concat_file = output_dir / f'{clip_id}_concat.txt'
            with open(concat_file, 'w') as f:
                for seg in segments:
                    seg_path = seg.get('file_path', '')
                    if Path(seg_path).exists():
                        f.write(f"file '{seg_path}'\n")

            # FFmpeg: concat + trim
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat', '-safe', '0',
                '-i', str(concat_file),
                '-ss', '0',
                '-c', 'copy',
                output_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            # Limpa arquivo temporário
            concat_file.unlink(missing_ok=True)

            if process.returncode == 0 and output_path.exists():
                file_size = output_path.stat().st_size
                await self._update_clip_status(
                    clip_id, 'completed',
                    file_path=str(output_path),
                    file_size=file_size,
                )
                print(f'Clip {clip_id} gerado: {output_path} ({file_size} bytes)')
            else:
                print(f'FFmpeg falhou para clip {clip_id}: {stderr.decode()}')
                await self._update_clip_status(clip_id, 'failed')

        except Exception as e:
            print(f'Erro ao construir clip {clip_id}: {e}')
            await self._update_clip_status(clip_id, 'failed')

    async def _update_clip_status(
        self, clip_id: str, status: str,
        file_path: str = None, file_size: int = None,
    ):
        """Atualiza status do clipe via API interna do Django"""
        data = {'status': status}
        if file_path:
            data['file_path'] = file_path
        if file_size:
            data['file_size'] = file_size

        try:
            await self.http_client.patch(
                f'{DJANGO_URL}/api/v1/clips/{clip_id}/',
                json=data,
            )
        except Exception as e:
            print(f'Erro ao atualizar clip {clip_id}: {e}')

    async def consume_queue(self):
        """Consome fila clip.build do RabbitMQ"""
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()
        queue = await channel.declare_queue('clip.build', durable=True)

        print('Clip Builder Worker iniciado. Aguardando mensagens...')

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    clip_data = json.loads(message.body)
                    await self.build_clip(clip_data)


async def main():
    worker = ClipBuilderWorker()
    await worker.consume_queue()


if __name__ == '__main__':
    asyncio.run(main())
