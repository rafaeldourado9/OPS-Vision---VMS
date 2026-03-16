import os
import tempfile
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.recordings.models import RecordingSegment
from tests.factories import CameraFactory, TenantFactory

pytestmark = pytest.mark.django_db


class TestStreamingProxyAPI:
    @pytest.fixture
    def setup_data(self):
        tenant = TenantFactory()
        other_tenant = TenantFactory()
        
        camera = CameraFactory(tenant=tenant)
        other_camera = CameraFactory(tenant=other_tenant)

        base_time = timezone.now().replace(microsecond=0)

        # Create a temporary pseudo-mp4 file with known content for testing byte-ranges
        fd, path = tempfile.mkstemp(suffix=".mp4")
        with os.fdopen(fd, "wb") as f:
            # Write exactly 100 bytes of data (b"0123456789" repeated 10 times)
            f.write(b"0123456789" * 10)

        segment = RecordingSegment.objects.create(
            camera=camera,
            tenant=tenant,
            start_time=base_time,
            end_time=base_time + timedelta(minutes=1),
            duration_seconds=60,
            file_path=path,
        )

        return {
            "tenant": tenant,
            "other_tenant": other_tenant,
            "camera": camera,
            "other_camera": other_camera,
            "segment": segment,
            "base_time": base_time,
            "file_path": path,
        }

    def teardown_method(self):
        # We'll clean up temp files in the test methods, but keeping this for safety
        pass

    def get_url(self, camera_id):
        return reverse("recordings:camera-stream", kwargs={"camera_id": camera_id})

    def test_returns_206_partial_content_with_range_header(self, api_client, setup_data):
        tenant = setup_data["tenant"]
        camera = setup_data["camera"]
        base_time = setup_data["base_time"]
        file_path = setup_data["file_path"]

        from rest_framework.test import APIClient
        from tests.factories import UserFactory
        user = UserFactory(tenant=tenant)
        client = APIClient()
        client.force_authenticate(user=user)
        url = self.get_url(camera.id)
        
        # Request bytes 10-19 (10 bytes total)
        response = client.get(
            url,
            data={"timestamp": base_time.isoformat()},
            HTTP_RANGE="bytes=10-19",
        )

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response["Content-Type"] == "video/mp4"
        assert response["Accept-Ranges"] == "bytes"
        assert response["Content-Length"] == "10"
        assert response["Content-Range"] == "bytes 10-19/100"
        
        # The content should be the second block of "0123456789"
        content = b"".join(response.streaming_content)
        assert content == b"0123456789"
        
        os.unlink(file_path)

    def test_returns_200_ok_full_file_without_range_header(self, api_client, setup_data):
        tenant = setup_data["tenant"]
        camera = setup_data["camera"]
        base_time = setup_data["base_time"]
        file_path = setup_data["file_path"]

        from rest_framework.test import APIClient
        from tests.factories import UserFactory
        user = UserFactory(tenant=tenant)
        client = APIClient()
        client.force_authenticate(user=user)
        url = self.get_url(camera.id)
        
        response = client.get(url, data={"timestamp": base_time.isoformat()})

        # If no Range header is provided, we should return the whole file
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "video/mp4"
        assert response["Accept-Ranges"] == "bytes"
        assert response["Content-Length"] == "100"
        
        content = b"".join(response.streaming_content)
        assert len(content) == 100
        assert content.startswith(b"0123456789")
        
        os.unlink(file_path)

    def test_returns_404_if_no_segment_exists(self, api_client, setup_data):
        tenant = setup_data["tenant"]
        camera = setup_data["camera"]
        base_time = setup_data["base_time"]
        file_path = setup_data["file_path"]

        from rest_framework.test import APIClient
        from tests.factories import UserFactory
        user = UserFactory(tenant=tenant)
        client = APIClient()
        client.force_authenticate(user=user)
        url = self.get_url(camera.id)
        
        # Request a timestamp that has no recording (2 hours later)
        response = client.get(url, data={"timestamp": (base_time + timedelta(hours=2)).isoformat()})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"detail": "Nenhuma gravação encontrada para o timestamp informado."}
        
        os.unlink(file_path)

    def test_tenant_isolation_enforced(self, api_client, setup_data):
        tenant = setup_data["tenant"]
        other_camera = setup_data["other_camera"]
        base_time = setup_data["base_time"]
        file_path = setup_data["file_path"]

        from rest_framework.test import APIClient
        from tests.factories import UserFactory
        user = UserFactory(tenant=tenant)
        client = APIClient()
        client.force_authenticate(user=user)
        url = self.get_url(other_camera.id)
        
        response = client.get(url, data={"timestamp": base_time.isoformat()})

        assert response.status_code == status.HTTP_404_NOT_FOUND

        os.unlink(file_path)
