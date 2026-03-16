from datetime import timedelta

import pytest
from django.utils.timezone import now
from rest_framework import status

from apps.recordings.models import RecordingSegment
from tests.factories import CameraFactory, TenantFactory, UserFactory

pytestmark = pytest.mark.django_db


class TestCameraPlaybackAPI:
    @pytest.fixture
    def setup_data(self, api_client):
        tenant = TenantFactory()
        other_tenant = TenantFactory()
        user = UserFactory(tenant=tenant)
        camera = CameraFactory(tenant=tenant)
        other_camera = CameraFactory(tenant=other_tenant)

        api_client.force_authenticate(user=user)

        base_time = now().replace(microsecond=0)

        # Segment: 10:00:00 - 10:01:00
        segment = RecordingSegment.objects.create(
            camera=camera,
            tenant=tenant,
            start_time=base_time,
            end_time=base_time + timedelta(seconds=60),
            duration_seconds=60,
            file_path="/recordings/cam01/2026/03/14/10-00-00.mp4",
        )

        # Segment for other tenant's camera
        RecordingSegment.objects.create(
            camera=other_camera,
            tenant=other_tenant,
            start_time=base_time,
            end_time=base_time + timedelta(seconds=60),
            duration_seconds=60,
            file_path="/recordings/cam02/2026/03/14/10-00-00.mp4",
        )

        return {
            "client": api_client,
            "camera": camera,
            "other_camera": other_camera,
            "base_time": base_time,
            "segment": segment,
        }

    def get_url(self, camera_id):
        return f"/api/v1/cameras/{camera_id}/playback/"

    def test_returns_playback_info_when_timestamp_inside_segment(self, setup_data):
        client = setup_data["client"]
        camera = setup_data["camera"]
        base_time = setup_data["base_time"]

        timestamp = (base_time + timedelta(seconds=30)).isoformat()
        url = self.get_url(camera.id)
        response = client.get(url, {"timestamp": timestamp})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["camera_id"] == camera.id
        assert data["file_path"] == "/recordings/cam01/2026/03/14/10-00-00.mp4"
        assert "segment_start" in data
        assert "segment_end" in data
        assert "offset_seconds" in data

    def test_returns_404_when_no_segment_at_timestamp(self, setup_data):
        client = setup_data["client"]
        camera = setup_data["camera"]
        base_time = setup_data["base_time"]

        # Timestamp far in the future
        timestamp = (base_time + timedelta(hours=5)).isoformat()
        url = self.get_url(camera.id)
        response = client.get(url, {"timestamp": timestamp})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_enforces_tenant_isolation(self, setup_data):
        client = setup_data["client"]
        other_camera = setup_data["other_camera"]
        base_time = setup_data["base_time"]

        timestamp = (base_time + timedelta(seconds=30)).isoformat()
        url = self.get_url(other_camera.id)
        response = client.get(url, {"timestamp": timestamp})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_offset_seconds_calculated_correctly(self, setup_data):
        client = setup_data["client"]
        camera = setup_data["camera"]
        base_time = setup_data["base_time"]

        timestamp = (base_time + timedelta(seconds=30)).isoformat()
        url = self.get_url(camera.id)
        response = client.get(url, {"timestamp": timestamp})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["offset_seconds"] == 30
