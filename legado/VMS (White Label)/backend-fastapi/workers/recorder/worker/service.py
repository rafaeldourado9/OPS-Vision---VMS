"""Recorder Worker — FFmpeg segmented recording with health monitoring.

Fixes from original:
1. Queue declared before consuming (prevents missed messages)
2. Full FFmpeg command + RTSP URL logged on startup
3. SEGMENT_DURATION configurable via env (default 60s)
4. Health probe: if FFmpeg produces no output in 30s, restart with exponential backoff
5. Proper segment registration with retry
"""

import asyncio
import os
import time
import httpx
from datetime import datetime, timedelta
from pathlib import Path
import aio_pika
import json
from prometheus_client import Counter, Gauge, Histogram
from common.metrics import MetricsServer, REGISTRY


RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
STORAGE_PATH = os.getenv('STORAGE_PATH', '/app/storage')
MEDIAMTX_URL = os.getenv('MEDIAMTX_URL', 'http://mediamtx:8888')
DJANGO_URL = os.getenv('DJANGO_INTERNAL_URL', 'http://django:8000')
SEGMENT_DURATION = int(os.getenv('SEGMENT_DURATION', '60'))  # T1.1.4 — lê SEGMENT_DURATION via os.environ com default 60
MAX_RESTART_DELAY = int(os.getenv('MAX_RESTART_DELAY', '120'))  # max backoff
HEALTH_TIMEOUT = int(os.getenv('HEALTH_TIMEOUT', '30'))  # no-output restart threshold
REGISTER_RETRY_COUNT = int(os.getenv('REGISTER_RETRY_COUNT', '3'))
REGISTER_RETRY_DELAY = int(os.getenv('REGISTER_RETRY_DELAY', '5'))

# ── Prometheus metrics ────────────────────────────────────────
recorder_active_streams = Gauge(
    'recorder_active_streams', 'Number of active recording streams',
    registry=REGISTRY,
)
recorder_segments_created = Counter(
    'recorder_segments_created_total', 'Total recording segments created',
    registry=REGISTRY,
)
recorder_ffmpeg_restarts = Counter(
    'recorder_ffmpeg_restarts_total', 'FFmpeg process restarts',
    registry=REGISTRY,
)
recorder_register_failures = Counter(
    'recorder_register_failures_total', 'Segment registration failures',
    registry=REGISTRY,
)
recorder_segment_duration = Histogram(
    'recorder_segment_duration_seconds', 'Actual segment file duration',
    registry=REGISTRY,
    buckets=(10, 30, 60, 120, 300, 600),
)


class RecorderWorker:
    def __init__(self):
        self.active_recordings: dict[str, dict] = {}
        self.http_client = httpx.AsyncClient(timeout=15)
        self._restart_counts: dict[str, int] = {}  # camera_id → consecutive restart count
        self._healthy = True
        print('[Recorder] Iniciando...', flush=True)
        print(f'[Recorder] Config: SEGMENT_DURATION={SEGMENT_DURATION}s '
              f'HEALTH_TIMEOUT={HEALTH_TIMEOUT}s STORAGE={STORAGE_PATH}', flush=True)

    # ── FFmpeg recording ──────────────────────────────────────

    async def start_recording(self, camera_id: str, tenant_id: str, stream_url: str):
        """Start FFmpeg segmented recording for a camera."""
        if camera_id in self.active_recordings:
            print(f'[Recorder] Camera {camera_id[:8]} já gravando, reiniciando...', flush=True)
            await self.stop_recording(camera_id)

        output_dir = Path(STORAGE_PATH) / 'recordings' / tenant_id / camera_id
        output_dir.mkdir(parents=True, exist_ok=True)

        output_pattern = str(output_dir / 'segment_%Y%m%d_%H%M%S.mp4')

        cmd = [
            'ffmpeg',
            '-hide_banner',
            '-loglevel', 'warning',
            '-rtsp_transport', 'tcp',
            '-timeout', '5000000',       # 5s connection/socket timeout (microseconds)
            '-i', stream_url,
            '-c', 'copy',
            '-f', 'segment',
            '-segment_time', str(SEGMENT_DURATION),
            '-segment_format', 'mp4',
            '-segment_atclocktime', '1',  # align segments to wall clock
            '-strftime', '1',
            '-reset_timestamps', '1',
            '-movflags', '+faststart',
            output_pattern,
        ]

        # T1.1.1 — logging completo do comando FFmpeg e URL RTSP antes do subprocess
        cmd_str = ' '.join(cmd)
        print(f'[Recorder] FFmpeg CMD: {cmd_str}', flush=True)
        print(f'[Recorder] Stream URL: {stream_url}', flush=True)
        print(f'[Recorder] Output dir: {output_dir}', flush=True)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            print('[Recorder] ERRO: ffmpeg não encontrado no PATH!', flush=True)
            return None
        except Exception as e:
            print(f'[Recorder] ERRO ao iniciar FFmpeg: {e}', flush=True)
            return None

        self.active_recordings[camera_id] = {
            'process': process,
            'tenant_id': tenant_id,
            'stream_url': stream_url,
            'output_dir': output_dir,
            'started_at': time.time(),
            'last_output': time.time(),
        }

        # Reset restart counter on successful start
        self._restart_counts[camera_id] = 0

        recorder_active_streams.set(len(self.active_recordings))
        print(f'[Recorder] Gravação iniciada: camera={camera_id[:8]} pid={process.pid}', flush=True)

        asyncio.create_task(self._log_ffmpeg_stderr(camera_id, process))
        asyncio.create_task(self._monitor_segments(camera_id, tenant_id, output_dir))
        asyncio.create_task(self._watch_process(camera_id, tenant_id, stream_url))
        asyncio.create_task(self._health_probe(camera_id))

        return process

    async def _log_ffmpeg_stderr(self, camera_id: str, process):
        """Consume FFmpeg stderr and log relevant lines. Updates last_output timestamp."""
        try:
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                text = line.decode(errors='replace').rstrip()
                if not text:
                    continue

                # Update last output timestamp for health probe
                rec = self.active_recordings.get(camera_id)
                if rec:
                    rec['last_output'] = time.time()

                # Log errors prominently, others at debug level
                lower = text.lower()
                if any(kw in lower for kw in ('error', 'fatal', 'failed', 'refused', 'timeout', 'no route', 'connection')):
                    print(f'[Recorder][FFmpeg][ERROR] camera={camera_id[:8]} {text}', flush=True)
                elif 'opening' in lower or 'output' in lower or 'segment' in lower:
                    print(f'[Recorder][FFmpeg] camera={camera_id[:8]} {text}', flush=True)
                    # "Opening" a new segment file means FFmpeg is producing output
                    if rec:
                        rec['last_output'] = time.time()
        except Exception:
            pass

    async def _health_probe(self, camera_id: str):  # T1.1.5 — health probe: se FFmpeg não produz output em HEALTH_TIMEOUT segundos, restart com backoff
        """Monitor FFmpeg health: restart if no output produced in HEALTH_TIMEOUT seconds."""
        while camera_id in self.active_recordings:
            await asyncio.sleep(10)
            rec = self.active_recordings.get(camera_id)
            if not rec:
                break

            elapsed = time.time() - rec['last_output']
            if elapsed > HEALTH_TIMEOUT:
                print(f'[Recorder] Health probe FAILED: camera={camera_id[:8]} '
                      f'no output for {elapsed:.0f}s (threshold={HEALTH_TIMEOUT}s)', flush=True)
                # Let _watch_process handle the restart
                try:
                    rec['process'].terminate()
                except ProcessLookupError:
                    pass
                break

    async def _watch_process(self, camera_id: str, tenant_id: str, stream_url: str):
        """Monitor FFmpeg process and restart with exponential backoff on crash."""
        recording = self.active_recordings.get(camera_id)
        if not recording:
            return
        process = recording['process']
        exit_code = await process.wait()

        if camera_id not in self.active_recordings:
            return

        del self.active_recordings[camera_id]
        recorder_active_streams.set(len(self.active_recordings))

        # Exponential backoff: 5s, 10s, 20s, 40s... up to MAX_RESTART_DELAY
        restart_count = self._restart_counts.get(camera_id, 0) + 1
        self._restart_counts[camera_id] = restart_count
        delay = min(5 * (2 ** (restart_count - 1)), MAX_RESTART_DELAY)

        print(f'[Recorder] FFmpeg encerrou: camera={camera_id[:8]} exit={exit_code} '
              f'restart #{restart_count} em {delay}s', flush=True)
        recorder_ffmpeg_restarts.inc()

        await asyncio.sleep(delay)

        # Only restart if not explicitly stopped
        if camera_id not in self.active_recordings:
            print(f'[Recorder] Re-iniciando gravação: camera={camera_id[:8]}', flush=True)
            await self.start_recording(camera_id, tenant_id, stream_url)

    # ── Segment monitoring ────────────────────────────────────

    async def _monitor_segments(self, camera_id: str, tenant_id: str, output_dir: Path):
        """Monitor new segments and register them in Django."""
        processed_files: set[Path] = set()

        while camera_id in self.active_recordings:
            try:
                for file_path in sorted(output_dir.glob('segment_*.mp4')):
                    if file_path in processed_files:
                        continue

                    # Wait for file to stabilize (FFmpeg may still be writing)
                    await asyncio.sleep(3)

                    # Check file size > 0 and not growing
                    try:
                        size1 = file_path.stat().st_size
                        if size1 == 0:
                            continue
                        await asyncio.sleep(2)
                        size2 = file_path.stat().st_size
                        if size2 != size1:
                            # Still being written, skip for now
                            continue
                    except FileNotFoundError:
                        continue

                    try:
                        filename = file_path.stem
                        timestamp_str = filename.replace('segment_', '')
                        start_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        end_time = start_time + timedelta(seconds=SEGMENT_DURATION)

                        # Store relative path for portability
                        relative_path = str(file_path).replace(STORAGE_PATH, '').lstrip('/\\')

                        success = await self._register_segment_with_retry(
                            camera=camera_id,
                            start_time=start_time.isoformat(),
                            end_time=end_time.isoformat(),
                            file_path=relative_path,
                            file_size=size2,
                        )
                        if success:
                            recorder_segment_duration.observe(SEGMENT_DURATION)
                    except Exception as e:
                        print(f'[Recorder] Erro processando segmento {file_path}: {e}', flush=True)

                    processed_files.add(file_path)
            except Exception as e:
                print(f'[Recorder] Erro no monitor de segmentos: {e}', flush=True)

            await asyncio.sleep(15)

    async def _register_segment_with_retry(self, **kwargs) -> bool:
        """Register segment in Django with retries."""
        # T1.1.3 — retry com backoff exponencial no registro de segmentos (POST ao Django)
        for attempt in range(1, REGISTER_RETRY_COUNT + 1):
            try:
                response = await self.http_client.post(
                    f'{DJANGO_URL}/api/v1/internal/segments/',
                    json=kwargs,
                )
                if response.status_code in (200, 201):
                    recorder_segments_created.inc()
                    camera_short = kwargs['camera'][:8] if 'camera' in kwargs else '???'
                    print(f'[Recorder] Segmento registrado: camera={camera_short} '
                          f'start={kwargs.get("start_time")}', flush=True)
                    return True
                elif response.status_code == 400:
                    print(f'[Recorder] Registro rejeitado (400): {response.text}', flush=True)
                    return False  # Don't retry validation errors
                else:
                    print(f'[Recorder] Registro falhou ({response.status_code}): {response.text}', flush=True)
            except Exception as e:
                print(f'[Recorder] Registro erro (attempt {attempt}/{REGISTER_RETRY_COUNT}): {e}', flush=True)

            if attempt < REGISTER_RETRY_COUNT:
                delay = REGISTER_RETRY_DELAY * (2 ** (attempt - 1))  # T1.1.3 — backoff exponencial: 5s, 10s, 20s...
                print(f'[Recorder] Retry em {delay}s (attempt {attempt}/{REGISTER_RETRY_COUNT})', flush=True)
                await asyncio.sleep(delay)

        recorder_register_failures.inc()
        return False

    # ── Stop ──────────────────────────────────────────────────

    async def stop_recording(self, camera_id: str):
        """Stop recording for a camera."""
        if camera_id in self.active_recordings:
            recording = self.active_recordings.pop(camera_id)
            try:
                recording['process'].terminate()
                await asyncio.wait_for(recording['process'].wait(), timeout=10)
            except asyncio.TimeoutError:
                recording['process'].kill()
            except ProcessLookupError:
                pass
            recorder_active_streams.set(len(self.active_recordings))
            print(f'[Recorder] Gravação parada: camera={camera_id[:8]}', flush=True)

    # ── Queue consumer ────────────────────────────────────────

    async def consume_queue(self):
        """Consume RabbitMQ queues (recording.start and recording.stop)."""
        # Retry connection with backoff
        connection = None
        for attempt in range(1, 11):
            try:
                connection = await aio_pika.connect_robust(RABBITMQ_URL)
                break
            except Exception as e:
                delay = min(5 * attempt, 30)
                print(f'[Recorder] RabbitMQ connection failed (attempt {attempt}): {e}. '
                      f'Retrying in {delay}s...', flush=True)
                await asyncio.sleep(delay)

        if connection is None:
            print('[Recorder] FATAL: Could not connect to RabbitMQ after 10 attempts', flush=True)
            return

        channel = await connection.channel()

        # T1.1.2 — declara todas as queues RabbitMQ antes de consumir mensagens
        start_queue = await channel.declare_queue('recording.start', durable=True)
        stop_queue = await channel.declare_queue('recording.stop', durable=True)
        # Also declare queues we depend on existing
        await channel.declare_queue('camera.activated', durable=True)

        print('[Recorder] Queues declaradas: recording.start, recording.stop', flush=True)

        async def on_start(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    data = json.loads(message.body)
                    camera_id = data['camera_id']
                    tenant_id = data['tenant_id']
                    stream_url = data['stream_url']
                    print(f'[Recorder] recording.start recebido: camera={camera_id[:8]} '
                          f'stream={stream_url}', flush=True)
                    await self.start_recording(camera_id, tenant_id, stream_url)
                except Exception as e:
                    print(f'[Recorder] Erro processando recording.start: {e}', flush=True)

        async def on_stop(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    data = json.loads(message.body)
                    camera_id = data['camera_id']
                    print(f'[Recorder] recording.stop recebido: camera={camera_id[:8]}', flush=True)
                    await self.stop_recording(camera_id)
                except Exception as e:
                    print(f'[Recorder] Erro processando recording.stop: {e}', flush=True)

        await start_queue.consume(on_start)
        await stop_queue.consume(on_stop)
        print('[Recorder] Aguardando mensagens...', flush=True)

        # Start metrics server with health checks
        server = MetricsServer(port=9100, worker_name='recorder')
        server.register_health_check('rabbitmq', lambda: connection and not connection.is_closed)
        server.register_health_check('ffmpeg', lambda: self._healthy)
        await server.start()

        await asyncio.Future()


async def main():
    worker = RecorderWorker()
    await worker.consume_queue()


if __name__ == '__main__':
    asyncio.run(main())
