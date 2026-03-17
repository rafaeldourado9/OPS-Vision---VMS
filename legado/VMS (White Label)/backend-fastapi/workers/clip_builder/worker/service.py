import asyncio
import os
from pathlib import Path

import aio_pika
import httpx
import json


RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
STORAGE_PATH = os.getenv('STORAGE_PATH', '/app/storage')
DJANGO_URL = os.getenv('DJANGO_INTERNAL_URL', 'http://django:8000')
MEDIA_ROOT = os.getenv('MEDIA_ROOT', '/app/storage')  # T4.4.1 — clips salvos em MEDIA_ROOT/clips/
CLIP_PRE_BUFFER_SECONDS = int(os.getenv('CLIP_PRE_BUFFER_SECONDS', '10'))   # T4.4.1 — pre-buffer configurável
CLIP_POST_BUFFER_SECONDS = int(os.getenv('CLIP_POST_BUFFER_SECONDS', '5'))  # T4.4.1 — post-buffer configurável
DJANGO_TIMEOUT = int(os.getenv('CLIP_BUILDER_DJANGO_TIMEOUT', '30'))        # segundos


class ClipBuilderWorker:
    """Constrói clipes de vídeo a partir de segmentos gravados."""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=DJANGO_TIMEOUT)

    async def build_clip(self, clip_data: dict):
        """T4.4.1 — Constrói clip de vídeo com pre-buffer de 10s e pós-buffer de 5s.

        Mensagem esperada: {event_id, camera_id, detected_at (ISO8601)}
        Intervalo buscado: [detected_at - 10s, detected_at + 5s]
        Output: MEDIA_ROOT/clips/{event_id}.mp4
        """
        from datetime import datetime, timedelta

        event_id = clip_data['event_id']
        camera_id = clip_data['camera_id']
        detected_at_str = clip_data['detected_at']

        # T4.4.1 — Calcular janela centrada na detecção (durações via env)
        detected_at = datetime.fromisoformat(detected_at_str.replace('Z', '+00:00'))
        window_start = (detected_at - timedelta(seconds=CLIP_PRE_BUFFER_SECONDS)).isoformat()
        window_end = (detected_at + timedelta(seconds=CLIP_POST_BUFFER_SECONDS)).isoformat()

        print(
            f'[ClipBuilder] Construindo clip: event={event_id[:8]} '
            f'window=[{window_start}, {window_end}]',
            flush=True,
        )

        try:
            # T4.4.1 — Buscar segmentos que cobrem o intervalo via Django
            response = await self.http_client.get(
                f'{DJANGO_URL}/api/v1/internal/segments/',
                params={'camera_id': camera_id, 'start': window_start, 'end': window_end},
            )
            response.raise_for_status()
            segments = response.json()

            if not segments:
                print(
                    f'[ClipBuilder] Nenhum segmento encontrado: event={event_id[:8]}',
                    flush=True,
                )
                return

            # T4.4.1 — Montar concat list; file_path é relativo a STORAGE_PATH
            output_dir = Path(MEDIA_ROOT) / 'clips'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f'{event_id}.mp4'
            concat_file = output_dir / f'{event_id}_concat.txt'

            valid_segments: list[str] = []
            with open(concat_file, 'w') as f:
                for seg in segments:
                    rel = seg.get('file_path', '')
                    abs_path = (
                        Path(rel) if Path(rel).is_absolute()
                        else Path(STORAGE_PATH) / rel
                    )
                    if abs_path.exists() and abs_path.stat().st_size > 0:
                        f.write(f"file '{abs_path}'\n")
                        valid_segments.append(str(abs_path))

            if not valid_segments:
                print(
                    f'[ClipBuilder] Nenhum arquivo de segmento acessível: event={event_id[:8]}',
                    flush=True,
                )
                concat_file.unlink(missing_ok=True)
                return

            # T4.4.1 — FFmpeg concat demuxer, sem re-encode (-c copy)
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat', '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                str(output_path),
            ]
            print(f'[ClipBuilder] FFmpeg CMD: {" ".join(cmd)}', flush=True)

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await process.communicate()
            finally:
                concat_file.unlink(missing_ok=True)  # sempre limpa, mesmo se FFmpeg não existe

            if process.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                file_size = output_path.stat().st_size
                # Caminho relativo a MEDIA_ROOT para armazenar no banco
                clip_rel = str(output_path.relative_to(Path(MEDIA_ROOT)))
                # T4.4.1 — POST ao Django para vincular clip ao AIEvent
                await self._link_clip_to_event(event_id, clip_rel, file_size)
                print(
                    f'[ClipBuilder] Clip gerado: event={event_id[:8]} '
                    f'size={file_size}B path={clip_rel}',
                    flush=True,
                )
            else:
                err = stderr.decode(errors='replace')[:300]
                print(f'[ClipBuilder] FFmpeg falhou: event={event_id[:8]} stderr={err}', flush=True)

        except Exception as e:
            import traceback
            print(f'[ClipBuilder] Erro: event={event_id[:8]} {e}', flush=True)
            traceback.print_exc()

    async def _link_clip_to_event(self, event_id: str, clip_path: str, file_size: int):
        """T4.4.1 — POST ao Django para vincular clip_path ao AIEvent."""
        try:
            response = await self.http_client.post(
                f'{DJANGO_URL}/api/v1/internal/events/{event_id}/clip/',
                json={'clip_path': clip_path, 'file_size': file_size},
            )
            if response.status_code not in (200, 201):
                print(
                    f'[ClipBuilder] Vinculação falhou ({response.status_code}): {response.text[:200]}',
                    flush=True,
                )
        except Exception as e:
            print(f'[ClipBuilder] Erro ao vincular clip ao evento {event_id[:8]}: {e}', flush=True)

    async def _update_clip_status(
        self, clip_id: str, status: str,
        file_path: str = None, file_size: int = None,
    ):
        """Atualiza status do clipe via API interna do Django (legado)"""  
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
        """Consome fila clip.create do RabbitMQ."""  # T4.4.1 — fila clip.create (publicada por T4.4.2)
        # Retry na conexão inicial — aio_pika.connect_robust só faz retry pós-connect
        connection = None
        for attempt in range(1, 11):
            try:
                connection = await aio_pika.connect_robust(RABBITMQ_URL)
                break
            except Exception as e:
                delay = min(5 * attempt, 30)
                print(f'[ClipBuilder] RabbitMQ indisponível (tentativa {attempt}): {e}. Retry em {delay}s', flush=True)
                await asyncio.sleep(delay)

        if connection is None:
            print('[ClipBuilder] FATAL: não foi possível conectar ao RabbitMQ após 10 tentativas', flush=True)
            return

        channel = await connection.channel()
        queue = await channel.declare_queue('clip.create', durable=True)

        print('[ClipBuilder] Aguardando mensagens em clip.create...', flush=True)

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
