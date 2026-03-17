from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils.timezone import now
from rest_framework import status

from apps.recordings.models import Clip, RecordingSegment
from tests.factories import CameraFactory, EventFactory, TenantFactory, UserFactory

pytestmark = pytest.mark.django_db


class TestClipGenerationAPI:
    @pytest.fixture
    def setup_data(self, api_client):
        tenant = TenantFactory()
        other_tenant = TenantFactory()
        user = UserFactory(tenant=tenant)
        camera = CameraFactory(tenant=tenant)
        other_camera = CameraFactory(tenant=other_tenant)

        api_client.force_authenticate(user=user)

        base_time = now().replace(microsecond=0)

        # Event at base_time + 15s (inside the segment)
        event = EventFactory(
            camera=camera,
            tenant=tenant,
        )
        # Force created_at to a known value
        from apps.events.models import Event
        Event.objects.filter(id=event.id).update(created_at=base_time + timedelta(seconds=15))
        event.refresh_from_db()

        # Recording segment covering 0s - 60s
        RecordingSegment.objects.create(
            camera=camera,
            tenant=tenant,
            start_time=base_time,
            end_time=base_time + timedelta(seconds=60),
            duration_seconds=60,
            file_path="/recordings/cam01/2026/03/14/10-00-00.mp4",
        )

        # Event for other tenant
        other_event = EventFactory(
            camera=other_camera,
            tenant=other_tenant,
        )

        return {
            "client": api_client,
            "camera": camera,
            "event": event,
            "other_event": other_event,
            "base_time": base_time,
        }

    def get_url(self, event_id):
        return f"/api/v1/events/{event_id}/clip/"

    @patch("apps.recordings.services._get_generate_clip_task")
    def test_post_returns_clip_id_and_pending_status(self, mock_task, setup_data):
        client = setup_data["client"]
        event = setup_data["event"]

        url = self.get_url(event.id)
        response = client.post(url)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "clip_id" in data
        assert data["status"] == "pending"

    @patch("apps.recordings.services._get_generate_clip_task")
    def test_clip_record_created_in_db(self, mock_task, setup_data):
        client = setup_data["client"]
        event = setup_data["event"]

        url = self.get_url(event.id)
        response = client.post(url)

        assert response.status_code == status.HTTP_201_CREATED
        clip = Clip.objects.get(id=response.json()["clip_id"])
        assert clip.event == event
        assert clip.camera == event.camera
        assert clip.tenant == event.tenant
        assert clip.status == "pending"

    @patch("apps.recordings.services._get_generate_clip_task")
    def test_celery_task_dispatched(self, mock_task, setup_data):
        client = setup_data["client"]
        event = setup_data["event"]

        url = self.get_url(event.id)
        client.post(url)

        mock_task.return_value.delay.assert_called_once()

    @patch("apps.recordings.services._get_generate_clip_task")
    def test_tenant_isolation_enforced(self, mock_task, setup_data):
        client = setup_data["client"]
        other_event = setup_data["other_event"]

        url = self.get_url(other_event.id)
        response = client.post(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
