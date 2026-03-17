"""Frame Grabber Worker — High-Availability edition for 500+ cameras.

Changes from original:
1. MotionGate extracted to motion.py (testable, Viseron-style erode+dilate)
2. RedisFrameCache replaces disk I/O (frame_cache.py)
3. CameraManager for multi-instance sharding (camera_manager.py)
4. Per-analytic queue routing (1 queue per ia_type, not generic ai.frame)
5. Graceful shutdown with camera release

Architecture:
  Camera (RTSP) → OpenCV → MotionGate (CPU) → RedisFrameCache → RabbitMQ per-analytic queues
"""

import asyncio
import base64
import hashlib
import json
import os
import signal
import time

import aio_pika
import cv2
import numpy as np
import redis.asyncio as aioredis
from prometheus_client import Counter, Gauge, Histogram
from common.metrics import MetricsServer, REGISTRY

from .motion import MotionGate, detect_motion_in_rois
from .frame_cache import RedisFrameCache
from .camera_manager import CameraManager

# ── Config ────────────────────────────────────────────────────
RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
STORAGE_PATH = os.getenv('STORAGE_PATH', '/app/storage')

THUMBNAIL_TTL = 300           # 5 min
THUMBNAIL_INTERVAL = 30       # Frames between thumbnail updates (~30s @ 1 FPS)
LOG_INTERVAL = 60             # Frames between log lines
BUFFER_DRAIN_COUNT = int(os.getenv('BUFFER_DRAIN_COUNT', '2'))
MOTION_THRESHOLD = float(os.getenv('MOTION_THRESHOLD', '0.5'))
MAX_FAIL_STREAK = int(os.getenv('MAX_FAIL_STREAK', '15'))
FRAME_INTERVAL = float(os.getenv('FRAME_INTERVAL', '0.33'))  # ~3 FPS capture
HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', '5'))

# Feature flags
USE_REDIS_CACHE = os.getenv('USE_REDIS_CACHE', '1') == '1'
USE_CAMERA_SHARDING = os.getenv('USE_CAMERA_SHARDING', '1') == '1'

# ── Prometheus metrics ────────────────────────────────────────
fg_frames_captured = Counter(
    'fg_frames_captured_total', 'Total frames captured',
    registry=REGISTRY,
)
fg_frames_skipped = Counter(
    'fg_frames_skipped_total', 'Frames skipped',
    ['reason'], registry=REGISTRY,
)
fg_frames_published = Counter(
    'fg_frames_published_total', 'Frames published to queues',
    registry=REGISTRY,
)
fg_cameras_active = Gauge(
    'fg_cameras_active', 'Number of active cameras',
    registry=REGISTRY,
)
fg_grab_latency = Histogram(
    'fg_grab_latency_seconds', 'Frame grab + process latency',
    registry=REGISTRY,
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

# Analytics that bypass motion filter
_ALWAYS_ON_TYPES = frozenset({'heatmap', 'lpr', 'facial'})

# ── Queue mapping: each ia_type gets its own queue ────────────
# GPU-bound: routed to specialized workers
_GPU_QUEUES = {
    'lpr': 'ai.frame.lpr',
    'facial': 'ai.frame.facial',
}

# CPU-bound analytics that need YOLO first: routed to yolo-worker
# The yolo-worker will then dispatch to ai.detect.{type}
_YOLO_QUEUE = 'ai.frame.yolo'
_YOLO_TYPES = frozenset({
    'object_detection', 'crowd', 'intrusion', 'loitering',
    'abandoned_object', 'queue', 'heatmap',
    'line_crossing', 'human_traffic', 'vehicle_traffic',
})

# All queues that need to be declared on startup
_ALL_QUEUES = list(_GPU_QUEUES.values()) + [_YOLO_QUEUE]


def _expand_roi_types(rois: list) -> list:
    """Expand ROIs that carry ia_types (multi-analytic mode) into one entry per type.

    A ROI with ia_types=['vehicle_traffic','lpr'] becomes two ROIs:
      {..., 'ia_type': 'vehicle_traffic'}  and  {..., 'ia_type': 'lpr'}
    This lets all existing routing logic remain unchanged.
    """
    result = []
    for roi in rois:
        types = roi.get('ia_types') or []
        if types:
            for t in types:
                result.append({**roi, 'ia_type': t})
        else:
            result.append(roi)
    return result


def _frame_hash(frame: np.ndarray) -> str:
    """Fast perceptual hash: 16x16 grayscale MD5. ~0.1ms."""
    small = cv2.resize(frame, (16, 16))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if len(small.shape) == 3 else small
    return hashlib.md5(gray.tobytes()).hexdigest()


def _open_stream(url: str) -> cv2.VideoCapture:
    """Open RTSP stream — runs in thread pool to avoid blocking the async event loop."""
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
    return cap


def _drain_and_read(cap: cv2.VideoCapture, drain_count: int) -> tuple:
    """Drain stale buffer frames then read the latest — runs in thread pool."""
    for _ in range(drain_count):
        cap.grab()
    return cap.read()


def _encode_inline(frame: np.ndarray) -> str:
    """Resize to 640x360, JPEG-encode, return base64 string — runs in thread pool."""
    small = cv2.resize(frame, (640, 360))
    _, buf = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buf.tobytes()).decode()


class FrameGrabberWorker:
    """High-availability frame grabber supporting 500+ cameras.

    Horizontally scalable: run N instances, each claims a shard of cameras
    via Redis-based CameraManager.
    """

    def __init__(self):
        self.active_cameras: dict[str, dict] = {}
        self._redis: aioredis.Redis | None = None
        self._redis_binary: aioredis.Redis | None = None
        self._frame_cache: RedisFrameCache | None = None
        self._camera_manager: CameraManager | None = None
        self._motion_gates: dict[str, MotionGate] = {}
        self._rmq_connection: aio_pika.RobustConnection | None = None
        self._rmq_channel: aio_pika.Channel | None = None
        self._shutting_down = False
        self._stats = {
            'frames_captured': 0,
            'frames_skipped_motion': 0,
            'frames_skipped_dup': 0,
            'frames_published': 0,
        }
        self._metrics_server: MetricsServer | None = None
        print(f'[FrameGrabber] Iniciando (sharding={USE_CAMERA_SHARDING}, '
              f'redis_cache={USE_REDIS_CACHE})', flush=True)

    # ── Redis ─────────────────────────────────────────────────

    async def _get_redis(self) -> aioredis.Redis:
        """Redis client with string responses (for thumbnails)."""
        if self._redis is None:
            self._redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    async def _get_redis_binary(self) -> aioredis.Redis:
        """Redis client with binary responses (for frame cache)."""
        if self._redis_binary is None:
            self._redis_binary = aioredis.from_url(REDIS_URL, decode_responses=False)
        return self._redis_binary

    async def _get_frame_cache(self) -> RedisFrameCache:
        if self._frame_cache is None:
            r = await self._get_redis_binary()
            self._frame_cache = RedisFrameCache(r, ttl=15, jpeg_quality=80)
        return self._frame_cache

    async def _get_camera_manager(self) -> CameraManager:
        if self._camera_manager is None:
            r = await self._get_redis_binary()
            self._camera_manager = CameraManager(r)
        return self._camera_manager

    # ── RabbitMQ ──────────────────────────────────────────────

    async def _get_channel(self) -> aio_pika.Channel:
        if self._rmq_connection is None or self._rmq_connection.is_closed:
            self._rmq_connection = await aio_pika.connect_robust(RABBITMQ_URL)
            self._rmq_channel = await self._rmq_connection.channel()
            # Declare all output queues
            for q in _ALL_QUEUES:
                await self._rmq_channel.declare_queue(q, durable=True)
        return self._rmq_channel

    async def _publish(self, routing_key: str, msg: dict):
        channel = await self._get_channel()
        await channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(msg).encode()),
            routing_key=routing_key,
        )

    # ── Camera lifecycle ──────────────────────────────────────

    async def start_grabbing(self, camera_id: str, tenant_id: str, stream_url: str,
                             rois: list | None = None, masks: list | None = None):
        if rois is None:
            rois = []
        if masks is None:
            masks = []

        # Camera sharding: check if this instance should own this camera
        if USE_CAMERA_SHARDING:
            mgr = await self._get_camera_manager()
            if not await mgr.try_claim(camera_id):
                return  # Another instance owns this camera

        if camera_id in self.active_cameras:
            prev_count = len(self.active_cameras[camera_id]['rois'])
            self.active_cameras[camera_id]['rois'] = rois
            self.active_cameras[camera_id]['masks'] = masks
            print(f'[FrameGrabber] Camera {camera_id[:8]} ROIs {prev_count}->{len(rois)} masks={len(masks)}', flush=True)
            return

        self.active_cameras[camera_id] = {
            'tenant_id': tenant_id,
            'stream_url': stream_url,
            'rois': rois,
            'masks': masks,
            'running': True,
            'frame_count': 0,
        }

        print(f'[FrameGrabber] Captura iniciada: camera={camera_id[:8]} '
              f'rois={len(rois)} masks={len(masks)} url={stream_url}', flush=True)
        fg_cameras_active.set(len(self.active_cameras))
        asyncio.create_task(self._grab_loop(camera_id))

    async def stop_grabbing(self, camera_id: str):
        if camera_id in self.active_cameras:
            self.active_cameras[camera_id]['running'] = False
            del self.active_cameras[camera_id]
            fg_cameras_active.set(len(self.active_cameras))
            # Release motion gate memory
            self._motion_gates.pop(camera_id, None)
            # Release camera claim
            if USE_CAMERA_SHARDING:
                mgr = await self._get_camera_manager()
                await mgr.release(camera_id)
            print(f'[FrameGrabber] Captura encerrada: camera={camera_id[:8]}', flush=True)

    # ── Main grab loop ────────────────────────────────────────

    async def _grab_loop(self, camera_id: str):
        """Per-camera capture loop with motion gating and inline frame transport."""
        camera_data = self.active_cameras.get(camera_id)
        if not camera_data:
            return

        stream_url = camera_data['stream_url']
        r = await self._get_redis()
        loop = asyncio.get_event_loop()
        gate = self._motion_gates.get(camera_id)
        if gate is None:
            gate = MotionGate()
            self._motion_gates[camera_id] = gate

        cap = None
        fail_streak = 0
        connect_failures = 0          # consecutive open() failures
        MAX_CONNECT_BACKOFF = 60      # cap backoff at 60s
        last_hash: str | None = None
        dup_count = 0

        try:
            while camera_data.get('running', False) and not self._shutting_down:
                # ── Stream connection ──────────────────────────
                if cap is None or not cap.isOpened():
                    if cap:
                        cap.release()
                    print(f'[FrameGrabber] Abrindo stream: {stream_url}', flush=True)
                    cap = await loop.run_in_executor(None, _open_stream, stream_url)
                    if cap.isOpened():
                        print(f'[FrameGrabber] Stream aberto: camera={camera_id[:8]}', flush=True)
                        connect_failures = 0
                    else:
                        connect_failures += 1
                        backoff = min(2 ** connect_failures, MAX_CONNECT_BACKOFF)
                        print(
                            f'[FrameGrabber] FALHA stream: camera={camera_id[:8]} '
                            f'tentativa={connect_failures} retry_in={backoff}s',
                            flush=True,
                        )
                        await asyncio.sleep(backoff)
                    last_hash = None
                    gate.reset()
                    continue

                # ── Drain + read in thread (non-blocking) ─────
                ret, frame = await loop.run_in_executor(
                    None, _drain_and_read, cap, BUFFER_DRAIN_COUNT
                )

                if not ret:
                    fail_streak += 1
                    if fail_streak >= MAX_FAIL_STREAK:
                        print(f'[FrameGrabber] {MAX_FAIL_STREAK} falhas, reconectando: camera={camera_id[:8]}', flush=True)
                        cap.release()
                        cap = None
                        fail_streak = 0
                        last_hash = None
                        await asyncio.sleep(5)
                    else:
                        await asyncio.sleep(0.1)
                    continue

                fail_streak = 0
                camera_data['frame_count'] += 1
                fc = camera_data['frame_count']
                height, width = frame.shape[:2]
                self._stats['frames_captured'] += 1
                fg_frames_captured.inc()

                # ── Periodic log ───────────────────────────────
                if fc % 30 == 1:
                    print(f'[FrameGrabber] camera={camera_id[:8]} frame#{fc}', flush=True)

                # ── Frame deduplication ────────────────────────
                current_hash = _frame_hash(frame)
                is_duplicate = current_hash == last_hash
                if is_duplicate:
                    dup_count += 1
                    self._stats['frames_skipped_dup'] += 1
                    fg_frames_skipped.labels(reason='duplicate').inc()
                    await asyncio.sleep(FRAME_INTERVAL)
                    continue
                else:
                    last_hash = current_hash
                    if dup_count > 0:
                        print(f'[FrameGrabber] camera={camera_id[:8]} skipped {dup_count} dups', flush=True)
                    dup_count = 0

                # ── Apply detection masks (black out regions) ──
                active_masks = camera_data.get('masks', [])
                if active_masks:
                    for mask in active_masks:
                        poly = mask.get('polygon', [])
                        if len(poly) >= 3:
                            pts = np.array(
                                [[int(p[0] * width), int(p[1] * height)] for p in poly],
                                dtype=np.int32,
                            )
                            cv2.fillPoly(frame, [pts], (0, 0, 0))

                # ── Thumbnail ──────────────────────────────────
                if fc % THUMBNAIL_INTERVAL == 1:
                    try:
                        thumb = cv2.resize(frame, (640, 360))
                        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])
                        b64 = base64.b64encode(buf.tobytes()).decode()
                        await r.setex(f'thumbnail:{camera_id}', THUMBNAIL_TTL, b64)
                    except Exception:
                        pass

                all_rois = camera_data['rois']
                if not all_rois:
                    await asyncio.sleep(1)
                    continue

                # ── Motion Gate (Viseron-style MOG2) ───────────
                motion_result = await loop.run_in_executor(None, gate.detect, frame)

                if motion_result.is_warmup:
                    await asyncio.sleep(1)
                    continue

                # Per-ROI motion check using fg_mask
                if motion_result.fg_mask is not None:
                    mask_h, mask_w = motion_result.fg_mask.shape[:2]
                    has_motion, triggered_rois = detect_motion_in_rois(
                        motion_result.fg_mask, all_rois, mask_w, mask_h,
                        area_threshold=MOTION_THRESHOLD,
                        always_on_types=_ALWAYS_ON_TYPES,
                    )
                else:
                    has_motion = True
                    triggered_rois = all_rois

                if not has_motion:
                    self._stats['frames_skipped_motion'] += 1
                    fg_frames_skipped.labels(reason='no_motion').inc()
                    streak = gate.skip_streak
                    if streak == 30:
                        print(f'[FrameGrabber] camera={camera_id[:8]} sem movimento 30s', flush=True)
                    elif streak > 0 and streak % 300 == 0:
                        print(f'[FrameGrabber] camera={camera_id[:8]} sem movimento {streak}s', flush=True)
                    await asyncio.sleep(1)
                    continue

                if gate.skip_streak == 0 and motion_result.motion_ratio > 0:
                    # Just resumed from idle
                    pass

                # ── Encode frame inline + publish ──────────────
                t0 = time.monotonic()
                frame_b64 = await loop.run_in_executor(None, _encode_inline, frame)

                # ── Route to per-analytic queues ───────────────
                base_msg = {
                    'camera_id': camera_id,
                    'tenant_id': camera_data['tenant_id'],
                    'frame_b64': frame_b64,
                    'frame_key': None,   # legacy compat
                    'frame_path': None,  # legacy compat
                }

                await self._route_to_queues(base_msg, _expand_roi_types(triggered_rois))
                self._stats['frames_published'] += 1
                fg_frames_published.inc()
                fg_grab_latency.observe(time.monotonic() - t0)

                # ── Periodic stats log ─────────────────────────
                if fc % LOG_INTERVAL == 0:
                    print(
                        f'[FrameGrabber] camera={camera_id[:8]} '
                        f'fc={fc} rois={len(all_rois)} triggered={len(triggered_rois)} '
                        f'motion={motion_result.motion_ratio:.4f} '
                        f'shape={height}x{width}',
                        flush=True,
                    )

                await asyncio.sleep(FRAME_INTERVAL)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            import traceback
            print(f'[FrameGrabber] ERRO camera={camera_id[:8]}: {e}', flush=True)
            traceback.print_exc()
        finally:
            if cap:
                cap.release()
            print(f'[FrameGrabber] Loop encerrado: camera={camera_id[:8]}', flush=True)

    async def _route_to_queues(self, base_msg: dict, triggered_rois: list[dict]):
        """Route frame to per-analytic queues based on ia_type.

        GPU-bound analytics (lpr, facial) go to dedicated queues.
        YOLO-dependent analytics go to ai.frame.yolo (single inference, then fan-out).
        """
        # Group ROIs by destination queue
        yolo_rois: list[dict] = []
        gpu_rois: dict[str, list[dict]] = {}  # queue_name → rois

        for roi in triggered_rois:
            ia_type = roi.get('ia_type', '')
            if ia_type in _GPU_QUEUES:
                queue = _GPU_QUEUES[ia_type]
                gpu_rois.setdefault(queue, []).append(roi)
            elif ia_type in _YOLO_TYPES:
                yolo_rois.append(roi)

        # Publish to YOLO queue (single inference for all YOLO-dependent analytics)
        if yolo_rois:
            msg = {**base_msg, 'rois': yolo_rois}
            await self._publish(_YOLO_QUEUE, msg)

        # Publish to GPU-specific queues
        for queue_name, rois in gpu_rois.items():
            msg = {**base_msg, 'rois': rois}
            await self._publish(queue_name, msg)

    # ── Health checks ──────────────────────────────────────────

    async def _startup_sync(self):
        """Fetch all cameras with active ROIs from Django at startup.

        This ensures frame-grabbers recover state after any restart without
        requiring manual roi.updated republication.
        """
        import aiohttp

        django_url = os.getenv('DJANGO_INTERNAL_URL', 'http://django:8000')
        secret = os.getenv('INTERNAL_SECRET', 'internal-secret-change-me')
        url = f'{django_url}/api/internal/roi-sync/?secret={secret}'

        # Give Django a moment to be fully ready (especially on fresh deploy)
        await asyncio.sleep(5)

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        print(f'[FrameGrabber] Startup sync falhou: HTTP {resp.status}', flush=True)
                        return
                    data = await resp.json()

            cameras = data.get('cameras', [])
            print(f'[FrameGrabber] Startup sync: {len(cameras)} câmeras encontradas', flush=True)

            for cam in cameras:
                camera_id = cam['camera_id']
                if camera_id not in self.active_cameras:
                    await self.start_grabbing(
                        camera_id,
                        cam['tenant_id'],
                        cam['stream_url'],
                        cam['roi_list'],
                        cam.get('masks', []),
                    )
                    print(f'[FrameGrabber] Startup sync: câmera iniciada={camera_id[:8]}', flush=True)
                else:
                    print(f'[FrameGrabber] Startup sync: câmera já ativa={camera_id[:8]}', flush=True)

        except Exception as e:
            print(f'[FrameGrabber] Startup sync erro: {e}', flush=True)

    async def _check_redis(self):
        try:
            r = await self._get_redis()
            return await r.ping()
        except Exception:
            return False

    async def _check_rabbitmq(self):
        return self._rmq_connection is not None and not self._rmq_connection.is_closed

    # ── Queue consumers ───────────────────────────────────────

    async def _consume_roi_updated(self, channel: aio_pika.Channel):
        queue = await channel.declare_queue('roi.updated', durable=True)
        print('[FrameGrabber] Aguardando roi.updated...', flush=True)

        async def on_message(message: aio_pika.IncomingMessage):
            async with message.process():
                data = json.loads(message.body)
                camera_id = data['camera_id']
                roi_list = data['roi_list']
                masks = data.get('masks', [])
                tenant_id = data.get('tenant_id', '')
                stream_url = data.get('stream_url', '')

                print(f'[FrameGrabber] roi.updated: camera={camera_id[:8]} rois={len(roi_list)} masks={len(masks)}', flush=True)

                if not roi_list and camera_id in self.active_cameras:
                    self.active_cameras[camera_id]['rois'] = []
                    self.active_cameras[camera_id]['masks'] = masks
                elif camera_id in self.active_cameras:
                    self.active_cameras[camera_id]['rois'] = roi_list
                    self.active_cameras[camera_id]['masks'] = masks
                else:
                    await self.start_grabbing(camera_id, tenant_id, stream_url, roi_list, masks)

        await queue.consume(on_message)

    async def _consume_camera_activated(self, channel: aio_pika.Channel):
        queue = await channel.declare_queue('camera.activated', durable=True)
        print('[FrameGrabber] Aguardando camera.activated...', flush=True)

        async def on_message(message: aio_pika.IncomingMessage):
            async with message.process():
                data = json.loads(message.body)
                camera_id = data['camera_id']
                tenant_id = data.get('tenant_id', '')
                stream_url = data.get('stream_url', '')

                if not stream_url:
                    return

                print(f'[FrameGrabber] camera.activated: camera={camera_id[:8]}', flush=True)
                if camera_id not in self.active_cameras:
                    await self.start_grabbing(camera_id, tenant_id, stream_url, rois=[])

        await queue.consume(on_message)

    # ── Heartbeat + orphan recovery ───────────────────────────

    async def _heartbeat_loop(self):
        """Periodic stats logging and (when sharding enabled) orphan camera recovery."""
        mgr = await self._get_camera_manager() if USE_CAMERA_SHARDING else None
        while not self._shutting_down:
            try:
                if mgr:
                    await mgr.heartbeat()
                    await mgr.refresh_claims()

                print(
                    f'[FrameGrabber] heartbeat: cameras={len(self.active_cameras)} '
                    f'captured={self._stats["frames_captured"]} '
                    f'published={self._stats["frames_published"]} '
                    f'skip_motion={self._stats["frames_skipped_motion"]} '
                    f'skip_dup={self._stats["frames_skipped_dup"]}',
                    flush=True,
                )
            except Exception as e:
                print(f'[FrameGrabber] heartbeat error: {e}', flush=True)
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    # ── Graceful shutdown ─────────────────────────────────────

    async def _shutdown(self):
        """Graceful shutdown: release all cameras, close connections."""
        print('[FrameGrabber] Shutdown iniciado...', flush=True)
        self._shutting_down = True

        # Stop all camera loops
        for cam_id in list(self.active_cameras):
            self.active_cameras[cam_id]['running'] = False

        # Wait for loops to finish
        await asyncio.sleep(2)

        # Release camera claims
        if USE_CAMERA_SHARDING and self._camera_manager:
            await self._camera_manager.release_all()

        # Close connections
        if self._rmq_connection and not self._rmq_connection.is_closed:
            await self._rmq_connection.close()
        if self._redis:
            await self._redis.close()
        if self._redis_binary:
            await self._redis_binary.close()

        print('[FrameGrabber] Shutdown completo.', flush=True)

    # ── Main entry ────────────────────────────────────────────

    async def run(self):
        """Main loop: consume queues + heartbeat in parallel."""
        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self._shutdown()))
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()

        # Declare all output queues
        for q in _ALL_QUEUES:
            await channel.declare_queue(q, durable=True)

        await self._consume_roi_updated(channel)
        await self._consume_camera_activated(channel)

        # Start heartbeat in background
        asyncio.create_task(self._heartbeat_loop())

        # Start metrics server
        self._metrics_server = MetricsServer(port=9100, worker_name='frame-grabber')
        self._metrics_server.register_health_check('redis', self._check_redis)
        self._metrics_server.register_health_check('rabbitmq', self._check_rabbitmq)
        await self._metrics_server.start()

        print(f'[FrameGrabber] Pronto. Queues: {_ALL_QUEUES}', flush=True)

        # Sync all existing ROIs from Django (handles frame-grabber restarts)
        asyncio.create_task(self._startup_sync())

        await asyncio.Future()


async def main():
    worker = FrameGrabberWorker()
    await worker.run()


if __name__ == '__main__':
    asyncio.run(main())
