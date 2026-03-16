"""Redis-backed frame cache replacing disk I/O in the AI pipeline.

Inspired by Viseron's SharedFrames, but adapted to our distributed
architecture where workers run in separate containers.

Instead of writing JPEG to disk (15-30ms) and workers reading from disk
(10-20ms), frames are stored in Redis with a short TTL.

Memory budget at 500 cameras @ 1 FPS:
  - Each frame: ~50KB (JPEG 640x360 Q80)
  - 500 cameras × 50KB = 25MB in Redis at any instant
  - TTL 15s → max 500 × 15 × 50KB = 375MB (worst case)
  - Well within a 1GB Redis allocation
"""

import time
import cv2
import numpy as np
from collections import deque

import redis.asyncio as aioredis


# Key prefix for frames
_FRAME_PREFIX = 'frame:'

# Ring buffer size per camera (5 min @ 1 FPS for lookback/pre-buffer)
_RING_BUFFER_SIZE = 300


class RedisFrameCache:
    """Store and retrieve camera frames via Redis instead of disk.

    Features:
    - JPEG compression before storage (configurable quality)
    - TTL auto-expiry (no manual cleanup needed)
    - Per-camera ring buffer for lookback/pre-buffer (local metadata)
    - Async API (aioredis)
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        ttl: int = 15,
        jpeg_quality: int = 80,
    ):
        self._redis = redis_client
        self._ttl = ttl
        self._jpeg_quality = jpeg_quality
        self._encode_params = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
        # Per-camera ring buffer: tracks (timestamp, redis_key) for lookback
        self._ring_buffers: dict[str, deque] = {}

    async def store(self, camera_id: str, frame: np.ndarray, timestamp: float | None = None) -> str:
        """Compress frame to JPEG and store in Redis with TTL.

        Returns the Redis key for retrieval.
        """
        ts = timestamp or time.time()
        key = f'{_FRAME_PREFIX}{camera_id}:{ts:.3f}'

        # Compress to JPEG bytes
        success, buf = cv2.imencode('.jpg', frame, self._encode_params)
        if not success:
            raise ValueError(f'Failed to encode frame for camera {camera_id}')

        # Store in Redis with TTL
        await self._redis.setex(key, self._ttl, buf.tobytes())

        # Track in ring buffer for lookback
        ring = self._ring_buffers.get(camera_id)
        if ring is None:
            ring = deque(maxlen=_RING_BUFFER_SIZE)
            self._ring_buffers[camera_id] = ring
        ring.append((ts, key))

        return key

    async def get(self, key: str) -> np.ndarray | None:
        """Retrieve and decode frame from Redis. Returns None if expired/missing."""
        data = await self._redis.get(key)
        if data is None:
            return None
        arr = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    async def get_bytes(self, key: str) -> bytes | None:
        """Retrieve raw JPEG bytes (avoids decode if not needed)."""
        return await self._redis.get(key)

    def get_lookback_keys(self, camera_id: str, seconds: float = 5.0) -> list[str]:
        """Get frame keys from last N seconds (for pre-buffer/lookback recording).

        Returns keys in chronological order.
        """
        ring = self._ring_buffers.get(camera_id)
        if not ring:
            return []
        cutoff = time.time() - seconds
        return [key for ts, key in ring if ts >= cutoff]

    def remove_camera(self, camera_id: str):
        """Clean up ring buffer when camera is removed."""
        self._ring_buffers.pop(camera_id, None)


async def load_frame(
    msg: dict,
    redis_client: aioredis.Redis | None = None,
) -> np.ndarray | None:
    """Universal frame loader: tries Redis first, falls back to disk.

    This is used by all workers (YOLO, LPR, Facial) to load frames
    regardless of whether they were stored via RedisFrameCache (new)
    or disk (legacy).

    Args:
        msg: Message dict with 'frame_key' (Redis) and/or 'frame_path' (disk).
        redis_client: Async Redis client. Required for Redis-cached frames.

    Returns:
        Decoded BGR numpy array, or None if frame not found.
    """
    # Try Redis first (new path)
    frame_key = msg.get('frame_key')
    if frame_key and redis_client is not None:
        try:
            data = await redis_client.get(frame_key)
            if data is not None:
                arr = np.frombuffer(data, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    return frame
        except Exception:
            pass  # Fall through to disk

    # Fallback: disk path (legacy compatibility)
    frame_path = msg.get('frame_path')
    if frame_path:
        import os
        if os.path.exists(frame_path):
            return cv2.imread(frame_path)

    return None
