"""Testes unitários para views de câmeras."""
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.cameras.services import CameraOfflineError
from tests.factories import CameraFactory, TenantFactory, UserFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestCameraViewSet:
    """Testes da API de câmeras."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_list_cameras_returns_only_tenant_cameras(self):
        """Lista somente câmeras do tenant do usuário."""
        # Arrange
        my_camera = CameraFactory(tenant=self.user.tenant)
        other_camera = CameraFactory()  # Outro tenant

        # Act
        response = self.client.get("/api/v1/cameras/")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        ids = [c["id"] for c in response.data["results"]]
        assert my_camera.id in ids
        assert other_camera.id not in ids

    @patch("apps.cameras.views.create_camera")
    def test_create_camera_returns_201(self, mock_create):
        """Criação retorna 201."""
        # Arrange
        mock_camera = CameraFactory.build(
            id=1,
            name="Nova Cam",
            location="Hall",
            rtsp_url="rtsp://10.0.0.1/stream",
            manufacturer="hikvision",
            retention_days=15,
            tenant=self.user.tenant,
        )
        mock_create.return_value = mock_camera

        data = {
            "name": "Nova Cam",
            "location": "Hall",
            "rtsp_url": "rtsp://10.0.0.1/stream",
            "manufacturer": "hikvision",
            "retention_days": 15,
        }

        # Act
        response = self.client.post("/api/v1/cameras/", data)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Nova Cam"
        mock_create.assert_called_once()

    def test_create_camera_validates_required_fields(self):
        """Validação de campos obrigatórios."""
        # Arrange
        data = {}

        # Act
        response = self.client.post("/api/v1/cameras/", data)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data
        assert "location" in response.data
        assert "rtsp_url" in response.data

    def test_get_camera_detail_returns_200(self):
        """Detalhe da câmera retorna 200."""
        # Arrange
        camera = CameraFactory(tenant=self.user.tenant)

        # Act
        response = self.client.get(f"/api/v1/cameras/{camera.id}/")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == camera.id
        assert response.data["name"] == camera.name

    def test_get_camera_from_other_tenant_returns_404(self):
        """Câmera de outro tenant retorna 404."""
        # Arrange
        other_camera = CameraFactory()  # Outro tenant

        # Act
        response = self.client.get(f"/api/v1/cameras/{other_camera.id}/")

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.cameras.views.update_camera")
    def test_update_camera_returns_200(self, mock_update):
        """Atualização retorna 200."""
        # Arrange
        camera = CameraFactory(tenant=self.user.tenant)
        mock_update.return_value = camera

        data = {
            "name": "Nome Atualizado",
            "location": "Local Atualizado",
        }

        # Act
        response = self.client.put(f"/api/v1/cameras/{camera.id}/", data)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        mock_update.assert_called_once()

    @patch("apps.cameras.views.update_camera")
    def test_partial_update_camera_returns_200(self, mock_update):
        """Atualização parcial (PATCH) retorna 200."""
        # Arrange
        camera = CameraFactory(tenant=self.user.tenant)
        mock_update.return_value = camera

        data = {"name": "Apenas Nome"}

        # Act
        response = self.client.patch(f"/api/v1/cameras/{camera.id}/", data)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        mock_update.assert_called_once()

    @patch("apps.cameras.views.delete_camera")
    def test_delete_camera_returns_204(self, mock_delete):
        """Deleção retorna 204."""
        # Arrange
        camera = CameraFactory(tenant=self.user.tenant)

        # Act
        response = self.client.delete(f"/api/v1/cameras/{camera.id}/")

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_delete.assert_called_once_with(camera.id)

    @patch("apps.cameras.views.get_camera_stream_url")
    def test_get_stream_url_returns_url(self, mock_get_url):
        """Endpoint stream-url retorna URL."""
        # Arrange
        camera = CameraFactory(tenant=self.user.tenant)
        mock_get_url.return_value = "http://mediamtx:8889/tenant-1/cam-1"

        # Act
        response = self.client.get(f"/api/v1/cameras/{camera.id}/stream-url/")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert "url" in response.data
        assert response.data["url"] == "http://mediamtx:8889/tenant-1/cam-1"

    @patch("apps.cameras.views.get_camera_stream_url")
    def test_get_stream_url_offline_camera_returns_400(self, mock_get_url):
        """Endpoint stream-url retorna 400 para câmera offline."""
        # Arrange
        camera = CameraFactory(tenant=self.user.tenant)
        mock_get_url.side_effect = CameraOfflineError("Camera is offline")

        # Act
        response = self.client.get(f"/api/v1/cameras/{camera.id}/stream-url/")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data

    def test_unauthenticated_request_returns_401(self):
        """Requisição não autenticada retorna 401."""
        # Arrange
        self.client.force_authenticate(user=None)

        # Act
        response = self.client.get("/api/v1/cameras/")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_cameras_filters_by_tenant(self):
        """Lista filtra por tenant automaticamente."""
        # Arrange
        tenant1 = TenantFactory()
        tenant2 = TenantFactory()
        user1 = UserFactory(tenant=tenant1)

        cam1 = CameraFactory(tenant=tenant1)
        cam2 = CameraFactory(tenant=tenant1)
        cam3 = CameraFactory(tenant=tenant2)

        self.client.force_authenticate(user=user1)

        # Act
        response = self.client.get("/api/v1/cameras/")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        ids = [c["id"] for c in response.data["results"]]
        assert cam1.id in ids
        assert cam2.id in ids
        assert cam3.id not in ids

    @patch("apps.cameras.views.generate_rtmp_push_url")
    def test_push_config_returns_200(self, mock_generate):
        """Endpoint push-config retorna 200 com dados RTMP."""
        # Arrange
        camera = CameraFactory(tenant=self.user.tenant)
        mock_generate.return_value = {
            "rtmp_url": f"rtmp://localhost:1935/tenant-{self.user.tenant_id}",
            "stream_key": f"cam-{camera.id}",
            "full_url": f"rtmp://localhost:1935/tenant-{self.user.tenant_id}/cam-{camera.id}",
        }

        # Act
        response = self.client.get(f"/api/v1/cameras/{camera.id}/push-config/")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert "rtmp_url" in response.data
        assert "stream_key" in response.data
        assert "full_url" in response.data
        mock_generate.assert_called_once_with(camera.id, self.user.tenant_id)

    def test_push_config_other_tenant_returns_404(self):
        """push-config de câmera de outro tenant retorna 404."""
        # Arrange
        other_camera = CameraFactory()

        # Act
        response = self.client.get(f"/api/v1/cameras/{other_camera.id}/push-config/")

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_push_config_unauthenticated_returns_401(self):
        """push-config sem autenticação retorna 401."""
        # Arrange
        camera = CameraFactory(tenant=self.user.tenant)
        self.client.force_authenticate(user=None)

        # Act
        response = self.client.get(f"/api/v1/cameras/{camera.id}/push-config/")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
