"""Camera assignment and health monitoring for horizontally-scaled frame grabbers.

Supports N frame-grabber instances sharing 500 cameras via Redis-based
distributed locking. Each instance claims cameras it can handle, and
releases them on shutdown or failure.

Health protocol:
  - Each instance writes heartbeat to Redis every 5s
  - Cameras track last_frame_at timestamp
  - A supervisor (or peer instance) detects stale cameras and reassigns them

Sharding strategy:
  - camera_id hashed to instance_id → deterministic assignment
  - On instance failure, surviving instances claim orphaned cameras
"""

import hashlib
import os
import time

import redis.asyncio as aioredis

INSTANCE_ID = os.getenv('INSTANCE_ID', os.getenv('HOSTNAME', 'fg-0'))
HEARTBEAT_TTL = 15          # seconds — instance considered dead after this
HEARTBEAT_INTERVAL = 5      # seconds between heartbeats
CAMERA_STALE_AFTER = 30     # seconds without frame → camera considered stale
MAX_CAMERAS_PER_INSTANCE = int(os.getenv('MAX_CAMERAS_PER_INSTANCE', '170'))

# Redis key prefixes
_INSTANCE_KEY = 'fg:instance:'
_CAMERA_OWNER_KEY = 'fg:camera:'
_CAMERA_HEARTBEAT_KEY = 'fg:cam_hb:'


class CameraManager:
    """Manages camera-to-instance assignment with Redis-based coordination.

    Usage:
        manager = CameraManager(redis)
        if await manager.try_claim(camera_id):
            # This instance now owns this camera
            start_grabbing(camera_id)

        # Periodic:
        await manager.heartbeat()
        orphans = await manager.find_orphaned_cameras()
    """

    def __init__(self, redis_client: aioredis.Redis, instance_id: str = INSTANCE_ID):
        self._redis = redis_client
        self.instance_id = instance_id
        self._owned_cameras: set[str] = set()

    async def heartbeat(self):
        """Write instance heartbeat + camera frame timestamps."""
        pipe = self._redis.pipeline()
        pipe.setex(f'{_INSTANCE_KEY}{self.instance_id}', HEARTBEAT_TTL, str(time.time()))
        # Batch-update camera heartbeats
        for cam_id in self._owned_cameras:
            pipe.setex(f'{_CAMERA_HEARTBEAT_KEY}{cam_id}', CAMERA_STALE_AFTER, self.instance_id)
        await pipe.execute()

    async def try_claim(self, camera_id: str) -> bool:
        """Try to claim ownership of a camera. Returns True if successful.

        Uses Redis SETNX for atomic claim — only one instance wins.
        """
        if len(self._owned_cameras) >= MAX_CAMERAS_PER_INSTANCE:
            return False

        key = f'{_CAMERA_OWNER_KEY}{camera_id}'
        # SETNX: only set if not exists
        claimed = await self._redis.set(key, self.instance_id, nx=True, ex=HEARTBEAT_TTL * 2)
        if claimed:
            self._owned_cameras.add(camera_id)
            return True

        # Check if we already own it
        owner = await self._redis.get(key)
        if owner and owner.decode() == self.instance_id:
            self._owned_cameras.add(camera_id)
            return True

        return False

    async def release(self, camera_id: str):
        """Release ownership of a camera."""
        key = f'{_CAMERA_OWNER_KEY}{camera_id}'
        owner = await self._redis.get(key)
        if owner and owner.decode() == self.instance_id:
            await self._redis.delete(key)
        self._owned_cameras.discard(camera_id)

    async def release_all(self):
        """Release all cameras (call on shutdown)."""
        pipe = self._redis.pipeline()
        for cam_id in list(self._owned_cameras):
            pipe.delete(f'{_CAMERA_OWNER_KEY}{cam_id}')
        await pipe.execute()
        self._owned_cameras.clear()

    async def refresh_claims(self):
        """Refresh TTL on all owned cameras (prevent expiry while alive)."""
        pipe = self._redis.pipeline()
        for cam_id in self._owned_cameras:
            pipe.expire(f'{_CAMERA_OWNER_KEY}{cam_id}', HEARTBEAT_TTL * 2)
        await pipe.execute()

    async def find_orphaned_cameras(self, all_camera_ids: list[str]) -> list[str]:
        """Find cameras whose owning instance has died.

        Checks if the camera's owner instance still has a heartbeat.
        Returns list of camera_ids that can be claimed.
        """
        orphans = []
        pipe = self._redis.pipeline()
        for cam_id in all_camera_ids:
            pipe.get(f'{_CAMERA_OWNER_KEY}{cam_id}')
        owners = await pipe.execute()

        # Check which owners are still alive
        alive_instances: dict[str, bool] = {}
        for cam_id, owner_bytes in zip(all_camera_ids, owners):
            if owner_bytes is None:
                # No owner — available
                orphans.append(cam_id)
                continue

            owner = owner_bytes.decode() if isinstance(owner_bytes, bytes) else str(owner_bytes)
            if owner == self.instance_id:
                continue  # We own it

            if owner not in alive_instances:
                hb = await self._redis.get(f'{_INSTANCE_KEY}{owner}')
                alive_instances[owner] = hb is not None

            if not alive_instances[owner]:
                # Owner is dead — claim
                orphans.append(cam_id)

        return orphans

    @property
    def owned_cameras(self) -> set[str]:
        return self._owned_cameras.copy()

    @property
    def camera_count(self) -> int:
        return len(self._owned_cameras)

    @staticmethod
    def preferred_instance(camera_id: str, num_instances: int) -> int:
        """Deterministic camera-to-instance mapping via consistent hashing.

        Returns instance index (0..num_instances-1).
        """
        h = int(hashlib.md5(camera_id.encode()).hexdigest(), 16)
        return h % num_instances
