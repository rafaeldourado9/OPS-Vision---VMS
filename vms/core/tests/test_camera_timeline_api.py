from datetime import timedelta

import pytest
from django.utils.timezone import now
from rest_framework import status

from apps.recordings.models import RecordingSegment
from tests.factories import CameraFactory, TenantFactory, UserFactory

pytestmark = pytest.mark.django_db


class TestCameraTimelineAPI:
    @pytest.fixture
    def setup_data(self, api_client):
        tenant = TenantFactory()
        other_tenant = TenantFactory()
        user = UserFactory(tenant=tenant)
        camera = CameraFactory(tenant=tenant)
        other_camera = CameraFactory(tenant=other_tenant)

        # Authenticate user
        api_client.force_authenticate(user=user)

        base_time = now()

        # Segment 1: completely within window
        RecordingSegment.objects.create(
            camera=camera,
            tenant=tenant,
            start_time=base_time - timedelta(minutes=30),
            end_time=base_time - timedelta(minutes=29),
            duration_seconds=60,
            file_path="/fake1",
        )

        # Segment 2: starts outside left, ends within window
        RecordingSegment.objects.create(
            camera=camera,
            tenant=tenant,
            start_time=base_time - timedelta(minutes=61),
            end_time=base_time - timedelta(minutes=59),
            duration_seconds=120,
            file_path="/fake2",
        )

        # Segment 3: starts within, ends outside right window
        RecordingSegment.objects.create(
            camera=camera,
            tenant=tenant,
            start_time=base_time - timedelta(minutes=1),
            end_time=base_time + timedelta(minutes=1),
            duration_seconds=120,
            file_path="/fake3",
        )

        # Segment 4: fully outside window (too old)
        RecordingSegment.objects.create(
            camera=camera,
            tenant=tenant,
            start_time=base_time - timedelta(hours=2),
            end_time=base_time - timedelta(hours=1, minutes=59),
            duration_seconds=60,
            file_path="/fake4",
        )

        # Segment 5: belongs to other tenant/camera (within window time)
        RecordingSegment.objects.create(
            camera=other_camera,
            tenant=other_tenant,
            start_time=base_time - timedelta(minutes=30),
            end_time=base_time - timedelta(minutes=29),
            duration_seconds=60,
            file_path="/fake5",
        )

        return {
            "client": api_client,
            "camera": camera,
            "base_time": base_time,
            "other_camera": other_camera,
        }

    def get_url(self, camera_id):
        return f"/api/v1/cameras/{camera_id}/timeline/"

    def test_timeline_returns_segments_within_range(self, setup_data):
        client = setup_data["client"]
        camera = setup_data["camera"]
        base_time = setup_data["base_time"]

        from_time = (base_time - timedelta(hours=1)).isoformat()
        to_time = base_time.isoformat()

        url = self.get_url(camera.id)
        response = client.get(url, {"from": from_time, "to": to_time})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return 3 segments: Segment 2 (overlaps start), Segment 1 (inside), Segment 3 (overlaps end)
        assert len(data) == 3

        # Verify ordering by start_time
        assert data[0]["start"] < data[1]["start"]
        assert data[1]["start"] < data[2]["start"]

    def test_timeline_returns_empty_when_no_recordings(self, setup_data):
        client = setup_data["client"]
        camera = setup_data["camera"]
        base_time = setup_data["base_time"]

        # Request window far in the future
        from_time = (base_time + timedelta(days=1)).isoformat()
        to_time = (base_time + timedelta(days=2)).isoformat()

        url = self.get_url(camera.id)
        response = client.get(url, {"from": from_time, "to": to_time})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

    def test_timeline_enforces_tenant_isolation(self, setup_data):
        client = setup_data["client"]
        other_camera = setup_data["other_camera"]
        base_time = setup_data["base_time"]

        from_time = (base_time - timedelta(hours=1)).isoformat()
        to_time = base_time.isoformat()

        # Try to access other tenant's camera
        url = self.get_url(other_camera.id)
        response = client.get(url, {"from": from_time, "to": to_time})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_timeline_missing_params(self, setup_data):
        client = setup_data["client"]
        camera = setup_data["camera"]

        url = self.get_url(camera.id)
        response = client.get(url)  # Missing from and to

        assert response.status_code == status.HTTP_400_BAD_REQUEST
