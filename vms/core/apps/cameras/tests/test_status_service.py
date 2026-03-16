"""Testes para o serviço set_camera_online."""
from unittest.mock import patch

import pytest

from apps.cameras.models import Camera
from apps.cameras.services import set_camera_online
from tests.factories import CameraFactory, TenantFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestSetCameraOnline:
    """Testes do serviço de atualização de status online."""

    def setup_method(self):
        self.tenant = TenantFactory()
        self.camera = CameraFactory(tenant=self.tenant, is_online=False)

    def test_set_online_updates_db(self):
        """Marca câmera como online no banco."""
        set_camera_online(self.camera.id, is_online=True)

        self.camera.refresh_from_db()
        assert self.camera.is_online is True

    def test_set_offline_updates_db(self):
        """Marca câmera como offline no banco."""
        self.camera.is_online = True
        self.camera.save()

        set_camera_online(self.camera.id, is_online=False)

        self.camera.refresh_from_db()
        assert self.camera.is_online is False

    @patch("apps.cameras.services.set_camera_status")
    def test_set_online_updates_cache(self, mock_set_cache):
        """Atualiza cache Redis ao marcar online."""
        set_camera_online(self.camera.id, is_online=True)

        mock_set_cache.assert_called_once_with(self.camera.id, True)

    @patch("apps.cameras.services.set_camera_status")
    def test_set_offline_updates_cache(self, mock_set_cache):
        """Atualiza cache Redis ao marcar offline."""
        set_camera_online(self.camera.id, is_online=False)

        mock_set_cache.assert_called_once_with(self.camera.id, False)

    def test_camera_not_found_raises_error(self):
        """Lança erro se câmera não existe."""
        with pytest.raises(Camera.DoesNotExist):
            set_camera_online(99999, is_online=True)

    def test_idempotent_online(self):
        """Chamar com mesmo valor não gera erro."""
        self.camera.is_online = True
        self.camera.save()

        set_camera_online(self.camera.id, is_online=True)  # mesma coisa

        self.camera.refresh_from_db()
        assert self.camera.is_online is True
