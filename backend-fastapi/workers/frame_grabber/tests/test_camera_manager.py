"""Tests for CameraManager — Redis-based camera sharding and failover."""
import pytest
from worker.camera_manager import CameraManager


class TestCameraManagerClaim:
    @pytest.mark.asyncio
    async def test_claim_new_camera(self, mock_redis):
        mgr = CameraManager(mock_redis, instance_id='fg-0')
        assert await mgr.try_claim('cam-1') is True
        assert 'cam-1' in mgr.owned_cameras
        assert mgr.camera_count == 1

    @pytest.mark.asyncio
    async def test_claim_already_owned_returns_true(self, mock_redis):
        mgr = CameraManager(mock_redis, instance_id='fg-0')
        await mgr.try_claim('cam-1')
        # Second claim by same instance
        assert await mgr.try_claim('cam-1') is True
        assert mgr.camera_count == 1

    @pytest.mark.asyncio
    async def test_claim_owned_by_other_returns_false(self, mock_redis):
        mgr1 = CameraManager(mock_redis, instance_id='fg-0')
        mgr2 = CameraManager(mock_redis, instance_id='fg-1')
        await mgr1.try_claim('cam-1')
        assert await mgr2.try_claim('cam-1') is False

    @pytest.mark.asyncio
    async def test_max_cameras_per_instance(self, mock_redis):
        mgr = CameraManager(mock_redis, instance_id='fg-0')
        # Override max for test
        import worker.camera_manager as cm
        original = cm.MAX_CAMERAS_PER_INSTANCE
        cm.MAX_CAMERAS_PER_INSTANCE = 3
        try:
            await mgr.try_claim('cam-1')
            await mgr.try_claim('cam-2')
            await mgr.try_claim('cam-3')
            assert await mgr.try_claim('cam-4') is False
            assert mgr.camera_count == 3
        finally:
            cm.MAX_CAMERAS_PER_INSTANCE = original


class TestCameraManagerRelease:
    @pytest.mark.asyncio
    async def test_release_camera(self, mock_redis):
        mgr = CameraManager(mock_redis, instance_id='fg-0')
        await mgr.try_claim('cam-1')
        await mgr.release('cam-1')
        assert 'cam-1' not in mgr.owned_cameras
        assert mgr.camera_count == 0

    @pytest.mark.asyncio
    async def test_release_all(self, mock_redis):
        mgr = CameraManager(mock_redis, instance_id='fg-0')
        await mgr.try_claim('cam-1')
        await mgr.try_claim('cam-2')
        await mgr.try_claim('cam-3')
        await mgr.release_all()
        assert mgr.camera_count == 0


class TestCameraManagerHeartbeat:
    @pytest.mark.asyncio
    async def test_heartbeat_writes_instance_key(self, mock_redis):
        mgr = CameraManager(mock_redis, instance_id='fg-0')
        await mgr.heartbeat()
        assert 'fg:instance:fg-0' in mock_redis._store

    @pytest.mark.asyncio
    async def test_heartbeat_writes_camera_keys(self, mock_redis):
        mgr = CameraManager(mock_redis, instance_id='fg-0')
        await mgr.try_claim('cam-1')
        await mgr.heartbeat()
        assert 'fg:cam_hb:cam-1' in mock_redis._store


class TestCameraManagerOrphanDetection:
    @pytest.mark.asyncio
    async def test_find_unclaimed_cameras(self, mock_redis):
        mgr = CameraManager(mock_redis, instance_id='fg-0')
        orphans = await mgr.find_orphaned_cameras(['cam-1', 'cam-2', 'cam-3'])
        # All cameras unclaimed
        assert len(orphans) == 3

    @pytest.mark.asyncio
    async def test_owned_cameras_not_orphaned(self, mock_redis):
        mgr = CameraManager(mock_redis, instance_id='fg-0')
        await mgr.try_claim('cam-1')
        orphans = await mgr.find_orphaned_cameras(['cam-1', 'cam-2'])
        assert 'cam-1' not in orphans
        assert 'cam-2' in orphans

    @pytest.mark.asyncio
    async def test_dead_instance_cameras_are_orphaned(self, mock_redis):
        """If owner instance has no heartbeat, cameras are orphaned."""
        mgr1 = CameraManager(mock_redis, instance_id='fg-0')
        mgr2 = CameraManager(mock_redis, instance_id='fg-1')

        # fg-0 claims cam-1 and writes heartbeat
        await mgr1.try_claim('cam-1')
        await mgr1.heartbeat()

        # fg-1 checks — cam-1 is alive, not orphaned
        orphans = await mgr2.find_orphaned_cameras(['cam-1'])
        assert 'cam-1' not in orphans

        # Simulate fg-0 death: remove heartbeat
        mock_redis._store.pop('fg:instance:fg-0', None)

        # Now cam-1 should be orphaned
        orphans = await mgr2.find_orphaned_cameras(['cam-1'])
        assert 'cam-1' in orphans


class TestCameraManagerHashing:
    def test_preferred_instance_deterministic(self):
        idx1 = CameraManager.preferred_instance('cam-abc-123', 3)
        idx2 = CameraManager.preferred_instance('cam-abc-123', 3)
        assert idx1 == idx2
        assert 0 <= idx1 < 3

    def test_preferred_instance_distributes(self):
        """Should distribute cameras roughly evenly across instances."""
        counts = [0, 0, 0]
        for i in range(100):
            idx = CameraManager.preferred_instance(f'cam-{i}', 3)
            counts[idx] += 1
        # Each instance should get at least 20% (rough check)
        assert all(c >= 15 for c in counts), f'Uneven distribution: {counts}'
