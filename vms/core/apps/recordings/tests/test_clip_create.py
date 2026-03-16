"""Testes para criação de clips via range de tempo (sem evento)."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.recordings.models import Clip
from apps.recordings.services import create_clip
from tests.factories import CameraFactory, TenantFactory, UserFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestCreateClipService:
    """Testes do serviço create_clip."""

    def setup_method(self):
        self.tenant = TenantFactory()
        self.camera = CameraFactory(tenant=self.tenant)
        self.start = timezone.now() - timedelta(minutes=10)
        self.end = timezone.now()

    @patch("apps.recordings.services._get_generate_clip_task")
    def test_creates_pending_clip(self, mock_get_task):
        """Clip criado com status PENDING."""
        mock_get_task.return_value.delay = lambda *a, **kw: None

        clip = create_clip(self.camera.id, self.tenant.id, self.start, self.end)

        assert clip.status == Clip.Status.PENDING
        assert clip.camera_id == self.camera.id
        assert clip.tenant_id == self.tenant.id
        assert clip.start_time == self.start
        assert clip.end_time == self.end
        assert clip.event is None

    @patch("apps.recordings.services._get_generate_clip_task")
    def test_dispatches_generate_clip_task(self, mock_get_task):
        """Tarefa de geração é despachada com o ID do clip."""
        mock_task = mock_get_task.return_value

        clip = create_clip(self.camera.id, self.tenant.id, self.start, self.end)

        mock_task.delay.assert_called_once_with(clip.id)


@pytest.mark.unit
@pytest.mark.django_db
class TestClipCreateEndpoint:
    """Testes do endpoint POST /api/v1/recordings/clips/."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.camera = CameraFactory(tenant=self.user.tenant)
        self.start = (timezone.now() - timedelta(minutes=10)).isoformat()
        self.end = timezone.now().isoformat()

    @patch("apps.recordings.views.create_clip")
    def test_returns_201_with_clip_info(self, mock_create):
        """POST válido retorna 201 com clip_id e status."""
        mock_create.return_value = Clip(
            id=42,
            camera=self.camera,
            tenant=self.user.tenant,
            start_time=timezone.now() - timedelta(minutes=10),
            end_time=timezone.now(),
            status=Clip.Status.PENDING,
        )

        response = self.client.post("/api/v1/recordings/clips/", {
            "camera_id": self.camera.id,
            "start_time": self.start,
            "end_time": self.end,
        })

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["clip_id"] == 42
        assert response.data["status"] == "pending"

    @patch("apps.recordings.views.create_clip")
    def test_calls_create_clip_service(self, mock_create):
        """View delega para o service create_clip."""
        mock_create.return_value = Clip(
            id=1,
            camera=self.camera,
            tenant=self.user.tenant,
            start_time=timezone.now() - timedelta(minutes=10),
            end_time=timezone.now(),
            status=Clip.Status.PENDING,
        )

        self.client.post("/api/v1/recordings/clips/", {
            "camera_id": self.camera.id,
            "start_time": self.start,
            "end_time": self.end,
        })

        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        assert kwargs["camera_id"] == self.camera.id
        assert kwargs["tenant_id"] == self.user.tenant_id

    def test_requires_authentication(self):
        """Sem autenticação retorna 401."""
        anon = APIClient()
        response = anon.post("/api/v1/recordings/clips/", {
            "camera_id": self.camera.id,
            "start_time": self.start,
            "end_time": self.end,
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("apps.recordings.views.create_clip")
    def test_camera_from_other_tenant_returns_404(self, mock_create):
        """Câmera de outro tenant retorna 404 (tenant isolation)."""
        other_camera = CameraFactory()  # Diferente tenant

        response = self.client.post("/api/v1/recordings/clips/", {
            "camera_id": other_camera.id,
            "start_time": self.start,
            "end_time": self.end,
        })

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_create.assert_not_called()

    def test_missing_camera_id_returns_400(self):
        """Sem camera_id retorna 400."""
        response = self.client.post("/api/v1/recordings/clips/", {
            "start_time": self.start,
            "end_time": self.end,
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_end_before_start_returns_400(self):
        """end_time anterior a start_time retorna 400."""
        response = self.client.post("/api/v1/recordings/clips/", {
            "camera_id": self.camera.id,
            "start_time": self.end,    # Invertido
            "end_time": self.start,
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST
