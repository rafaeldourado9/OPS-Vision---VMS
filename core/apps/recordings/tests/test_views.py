"""Testes para views de recordings: clips e storage."""
import os
import tempfile
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.recordings.models import Clip
from tests.factories import CameraFactory, EventFactory, TenantFactory, UserFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestClipDetailView:
    """Testes do endpoint GET /api/v1/clips/{id}/."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.camera = CameraFactory(tenant=self.user.tenant)
        self.event = EventFactory(tenant=self.user.tenant, camera=self.camera)

    def _make_clip(self, status=Clip.Status.PENDING, file_path=None):
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        return Clip.objects.create(
            tenant=self.user.tenant,
            camera=self.camera,
            event=self.event,
            start_time=now - timedelta(seconds=10),
            end_time=now + timedelta(seconds=20),
            status=status,
            file_path=file_path,
        )

    def test_detail_pending_clip_returns_200(self):
        """Detalhe de clip pendente retorna 200 com status."""
        clip = self._make_clip(status=Clip.Status.PENDING)

        response = self.client.get(f"/api/v1/clips/{clip.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == clip.id
        assert response.data["status"] == "pending"

    def test_detail_ready_clip_returns_200(self):
        """Detalhe de clip pronto retorna 200."""
        clip = self._make_clip(status=Clip.Status.READY, file_path="/tmp/clip_1.mp4")

        response = self.client.get(f"/api/v1/clips/{clip.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ready"

    def test_detail_wrong_tenant_returns_404(self):
        """Clip de outro tenant retorna 404."""
        other_tenant = TenantFactory()
        other_camera = CameraFactory(tenant=other_tenant)
        other_user = UserFactory(tenant=other_tenant)
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        other_clip = Clip.objects.create(
            tenant=other_tenant,
            camera=other_camera,
            start_time=now - timedelta(seconds=10),
            end_time=now + timedelta(seconds=20),
            status=Clip.Status.READY,
        )

        response = self.client.get(f"/api/v1/clips/{other_clip.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_detail_unauthenticated_returns_401(self):
        """Sem autenticação retorna 401."""
        clip = self._make_clip()
        self.client.force_authenticate(user=None)

        response = self.client.get(f"/api/v1/clips/{clip.id}/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.unit
@pytest.mark.django_db
class TestClipDownloadView:
    """Testes do endpoint GET /api/v1/clips/{id}/download/."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.camera = CameraFactory(tenant=self.user.tenant)
        self.event = EventFactory(tenant=self.user.tenant, camera=self.camera)

    def _make_clip(self, clip_status=Clip.Status.PENDING, file_path=None):
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        return Clip.objects.create(
            tenant=self.user.tenant,
            camera=self.camera,
            event=self.event,
            start_time=now - timedelta(seconds=10),
            end_time=now + timedelta(seconds=20),
            status=clip_status,
            file_path=file_path,
        )

    def test_download_ready_clip_serves_file(self):
        """Download de clip pronto serve o arquivo."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake mp4 content")
            tmp_path = f.name

        try:
            clip = self._make_clip(clip_status=Clip.Status.READY, file_path=tmp_path)

            response = self.client.get(f"/api/v1/clips/{clip.id}/download/")

            assert response.status_code == status.HTTP_200_OK
            assert response["Content-Type"] == "video/mp4"
            assert "attachment" in response.get("Content-Disposition", "")
        finally:
            os.unlink(tmp_path)

    def test_download_pending_clip_returns_409(self):
        """Download de clip não pronto retorna 409."""
        clip = self._make_clip(clip_status=Clip.Status.PENDING)

        response = self.client.get(f"/api/v1/clips/{clip.id}/download/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "status" in response.data

    def test_download_processing_clip_returns_409(self):
        """Download de clip em processamento retorna 409."""
        clip = self._make_clip(clip_status=Clip.Status.PROCESSING)

        response = self.client.get(f"/api/v1/clips/{clip.id}/download/")

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_download_failed_clip_returns_409(self):
        """Download de clip com falha retorna 409."""
        clip = self._make_clip(clip_status=Clip.Status.FAILED)

        response = self.client.get(f"/api/v1/clips/{clip.id}/download/")

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_download_ready_but_missing_file_returns_404(self):
        """Clip READY mas arquivo deletado do disco retorna 404."""
        clip = self._make_clip(
            clip_status=Clip.Status.READY,
            file_path="/nonexistent/path/clip_999.mp4",
        )

        response = self.client.get(f"/api/v1/clips/{clip.id}/download/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_download_wrong_tenant_returns_404(self):
        """Clip de outro tenant retorna 404."""
        other_tenant = TenantFactory()
        other_camera = CameraFactory(tenant=other_tenant)
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        other_clip = Clip.objects.create(
            tenant=other_tenant,
            camera=other_camera,
            start_time=now - timedelta(seconds=10),
            end_time=now + timedelta(seconds=20),
            status=Clip.Status.READY,
            file_path="/some/path.mp4",
        )

        response = self.client.get(f"/api/v1/clips/{other_clip.id}/download/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_download_filename_contains_clip_id(self):
        """Content-Disposition inclui o ID do clip no nome do arquivo."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake mp4 content")
            tmp_path = f.name

        try:
            clip = self._make_clip(clip_status=Clip.Status.READY, file_path=tmp_path)

            response = self.client.get(f"/api/v1/clips/{clip.id}/download/")

            assert str(clip.id) in response.get("Content-Disposition", "")
        finally:
            os.unlink(tmp_path)

    def test_download_unauthenticated_returns_401(self):
        """Sem autenticação retorna 401."""
        clip = self._make_clip()
        self.client.force_authenticate(user=None)

        response = self.client.get(f"/api/v1/clips/{clip.id}/download/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
