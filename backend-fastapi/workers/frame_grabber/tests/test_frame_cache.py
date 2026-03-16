"""Tests for RedisFrameCache — replaces disk I/O with Redis."""
import time

import cv2
import numpy as np
import pytest

from worker.frame_cache import RedisFrameCache, load_frame


class TestRedisFrameCacheStore:
    @pytest.mark.asyncio
    async def test_store_returns_redis_key(self, mock_redis):
        cache = RedisFrameCache(mock_redis)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        key = await cache.store("cam1", frame)
        assert key.startswith("frame:cam1:")
        assert key in mock_redis._store

    @pytest.mark.asyncio
    async def test_store_custom_timestamp(self, mock_redis):
        cache = RedisFrameCache(mock_redis)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        key = await cache.store("cam1", frame, timestamp=1234567890.123)
        assert "1234567890.123" in key

    @pytest.mark.asyncio
    async def test_store_compresses_to_jpeg(self, mock_redis):
        cache = RedisFrameCache(mock_redis, jpeg_quality=50)
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        key = await cache.store("cam1", frame)
        raw_bytes = mock_redis._store[key]
        # JPEG header starts with FF D8
        assert raw_bytes[:2] == b'\xff\xd8'


class TestRedisFrameCacheGet:
    @pytest.mark.asyncio
    async def test_roundtrip_preserves_shape(self, mock_redis):
        cache = RedisFrameCache(mock_redis, jpeg_quality=95)
        original = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        key = await cache.store("cam1", original)
        recovered = await cache.get(key)
        assert recovered is not None
        assert recovered.shape == original.shape

    @pytest.mark.asyncio
    async def test_roundtrip_approximate_pixel_match(self, mock_redis):
        cache = RedisFrameCache(mock_redis, jpeg_quality=95)
        original = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
        key = await cache.store("cam1", original)
        recovered = await cache.get(key)
        # JPEG is lossy — check mean absolute error is small
        mae = np.mean(np.abs(recovered.astype(int) - original.astype(int)))
        assert mae < 10, f'MAE too high: {mae:.1f}'

    @pytest.mark.asyncio
    async def test_get_missing_key_returns_none(self, mock_redis):
        cache = RedisFrameCache(mock_redis)
        result = await cache.get("frame:nonexistent:0.000")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_bytes_returns_raw_jpeg(self, mock_redis):
        cache = RedisFrameCache(mock_redis)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        key = await cache.store("cam1", frame)
        raw = await cache.get_bytes(key)
        assert raw is not None
        assert isinstance(raw, bytes)
        assert raw[:2] == b'\xff\xd8'


class TestRedisFrameCacheLookback:
    @pytest.mark.asyncio
    async def test_lookback_returns_recent_keys(self, mock_redis):
        cache = RedisFrameCache(mock_redis)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        keys = []
        for _ in range(10):
            keys.append(await cache.store("cam1", frame))
        lookback = cache.get_lookback_keys("cam1", seconds=60)
        assert len(lookback) == 10
        assert lookback == keys

    @pytest.mark.asyncio
    async def test_lookback_empty_for_unknown_camera(self, mock_redis):
        cache = RedisFrameCache(mock_redis)
        assert cache.get_lookback_keys("unknown_cam") == []

    @pytest.mark.asyncio
    async def test_ring_buffer_capped_at_300(self, mock_redis):
        cache = RedisFrameCache(mock_redis)
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        for _ in range(350):
            await cache.store("cam1", frame)
        assert len(cache._ring_buffers["cam1"]) == 300

    @pytest.mark.asyncio
    async def test_remove_camera_cleans_ring_buffer(self, mock_redis):
        cache = RedisFrameCache(mock_redis)
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        await cache.store("cam1", frame)
        assert "cam1" in cache._ring_buffers
        cache.remove_camera("cam1")
        assert "cam1" not in cache._ring_buffers


class TestLoadFrame:
    """Tests for the universal frame loader (Redis → disk fallback)."""

    @pytest.mark.asyncio
    async def test_loads_from_redis(self, mock_redis):
        cache = RedisFrameCache(mock_redis)
        frame = np.full((100, 100, 3), 42, dtype=np.uint8)
        key = await cache.store("cam1", frame)

        msg = {"frame_key": key, "frame_path": None}
        loaded = await load_frame(msg, redis_client=mock_redis)
        assert loaded is not None
        assert loaded.shape == (100, 100, 3)

    @pytest.mark.asyncio
    async def test_fallback_to_disk(self, tmp_path):
        frame = np.full((100, 100, 3), 42, dtype=np.uint8)
        path = str(tmp_path / "test.jpg")
        cv2.imwrite(path, frame)

        from unittest.mock import AsyncMock
        empty_redis = AsyncMock()
        empty_redis.get = AsyncMock(return_value=None)

        msg = {"frame_key": None, "frame_path": path}
        loaded = await load_frame(msg, redis_client=empty_redis)
        assert loaded is not None
        assert loaded.shape == (100, 100, 3)

    @pytest.mark.asyncio
    async def test_returns_none_if_no_source(self, mock_redis):
        msg = {"frame_key": None, "frame_path": None}
        loaded = await load_frame(msg, redis_client=mock_redis)
        assert loaded is None

    @pytest.mark.asyncio
    async def test_redis_failure_fallback_to_disk(self, tmp_path):
        """If Redis raises, should fall back to disk."""
        frame = np.full((100, 100, 3), 42, dtype=np.uint8)
        path = str(tmp_path / "fallback.jpg")
        cv2.imwrite(path, frame)

        from unittest.mock import AsyncMock
        failing_redis = AsyncMock()
        failing_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))

        msg = {"frame_key": "frame:cam1:123.456", "frame_path": path}
        loaded = await load_frame(msg, redis_client=failing_redis)
        assert loaded is not None


class TestRedisFrameCachePerformance:
    @pytest.mark.asyncio
    async def test_store_latency_under_10ms(self, mock_redis):
        """In-memory mock should be near-instant; real Redis ~2-5ms."""
        cache = RedisFrameCache(mock_redis)
        frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)

        # Warm up
        await cache.store("perf", frame)

        iterations = 50
        start = time.perf_counter()
        for _ in range(iterations):
            await cache.store("perf", frame)
        elapsed_per = (time.perf_counter() - start) / iterations

        # JPEG encode dominates — should be < 10ms for 720p
        assert elapsed_per < 0.050, f'Too slow: {elapsed_per*1000:.1f}ms'
