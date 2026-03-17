import os
import tempfile
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.recordings.models import RecordingSegment
from apps.recordings.services import cleanup_old_recordings
from tests.factories import CameraFactory, TenantFactory

pytestmark = pytest.mark.django_db


class TestRecordingCleanup:
    @pytest.fixture
    def setup_data(self):
        tenant = TenantFactory()
        # Camera has 7 days retention by default in CameraFactory
        camera = CameraFactory(tenant=tenant, retention_days=7)
        other_camera = CameraFactory(tenant=tenant, retention_days=3)

        base_time = timezone.now()

        # Create temporary files for segments
        fd1, path1 = tempfile.mkstemp(suffix=".mp4")
        os.close(fd1)
        
        fd2, path2 = tempfile.mkstemp(suffix=".mp4")
        os.close(fd2)

        fd3, path3 = tempfile.mkstemp(suffix=".mp4")
        os.close(fd3)

        fd4, path4 = tempfile.mkstemp(suffix=".mp4")
        os.close(fd4)

        # Segment 1: older than 7 days (Should be deleted)
        seg1 = RecordingSegment.objects.create(
            camera=camera,
            tenant=tenant,
            start_time=base_time - timedelta(days=8),
            end_time=base_time - timedelta(days=8) + timedelta(minutes=1),
            duration_seconds=60,
            file_path=path1,
        )

        # Segment 2: newer than 7 days (Should be kept)
        seg2 = RecordingSegment.objects.create(
            camera=camera,
            tenant=tenant,
            start_time=base_time - timedelta(days=6),
            end_time=base_time - timedelta(days=6) + timedelta(minutes=1),
            duration_seconds=60,
            file_path=path2,
        )

        # Segment 3: older than 3 days, (other_camera, Should be deleted)
        seg3 = RecordingSegment.objects.create(
            camera=other_camera,
            tenant=tenant,
            start_time=base_time - timedelta(days=4),
            end_time=base_time - timedelta(days=4) + timedelta(minutes=1),
            duration_seconds=60,
            file_path=path3,
        )
        
        # Segment 4: older than 7 days, but file is missing (graceful handling)
        os.unlink(path4)
        seg4 = RecordingSegment.objects.create(
            camera=camera,
            tenant=tenant,
            start_time=base_time - timedelta(days=10),
            end_time=base_time - timedelta(days=10) + timedelta(minutes=1),
            duration_seconds=60,
            file_path=path4,
        )

        return {
            "camera": camera,
            "other_camera": other_camera,
            "seg1": seg1,
            "seg2": seg2,
            "seg3": seg3,
            "seg4": seg4,
            "path1": path1,
            "path2": path2,
            "path3": path3,
        }

    def teardown_method(self):
        # Clean up any leftover temp files
        pass

    def test_cleanup_deletes_old_segments_and_files(self, setup_data):
        path1 = setup_data["path1"]
        seg1_id = setup_data["seg1"].id

        assert os.path.exists(path1)
        assert RecordingSegment.objects.filter(id=seg1_id).exists()

        cleanup_old_recordings()

        assert not os.path.exists(path1)
        assert not RecordingSegment.objects.filter(id=seg1_id).exists()

    def test_cleanup_keeps_segments_newer_than_retention(self, setup_data):
        path2 = setup_data["path2"]
        seg2_id = setup_data["seg2"].id

        assert os.path.exists(path2)
        assert RecordingSegment.objects.filter(id=seg2_id).exists()

        cleanup_old_recordings()

        # Should still exist
        assert os.path.exists(path2)
        assert RecordingSegment.objects.filter(id=seg2_id).exists()

        # cleanup
        if os.path.exists(path2):
            os.unlink(path2)

    def test_cleanup_handles_missing_files_gracefully(self, setup_data):
        seg4_id = setup_data["seg4"].id

        # File is already missing
        assert RecordingSegment.objects.filter(id=seg4_id).exists()

        # Should not crash and should delete the DB record
        cleanup_old_recordings()

        assert not RecordingSegment.objects.filter(id=seg4_id).exists()

    def test_cleanup_processes_multiple_cameras_correctly(self, setup_data):
        path3 = setup_data["path3"]
        seg3_id = setup_data["seg3"].id

        assert os.path.exists(path3)
        assert RecordingSegment.objects.filter(id=seg3_id).exists()

        cleanup_old_recordings()

        # other_camera has 3 days retention, so seg3 (4 days old) should be deleted
        assert not os.path.exists(path3)
        assert not RecordingSegment.objects.filter(id=seg3_id).exists()
