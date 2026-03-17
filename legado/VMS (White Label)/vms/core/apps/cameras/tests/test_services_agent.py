"""Testes unitários para integração câmera-agent em services."""
from unittest.mock import MagicMock, patch

import pytest

from apps.cameras.models import Camera
from apps.cameras.services import CameraCreateInput, create_camera
from tests.factories import AgentFactory, TenantFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestCreateCameraWithAgent:
    """Testes de criação de câmera no modo agent (RTMP push)."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.tenant = TenantFactory()
        self.agent = AgentFactory(tenant=self.tenant)

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_creates_camera_with_agent(self, mock_publish, mock_mtx_cls):
        """Cria câmera associada a um agent."""
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        data = CameraCreateInput(
            name="Cam Agent",
            location="Filial SP",
            rtsp_url="rtsp://192.168.1.100:554/stream",
            manufacturer="intelbras",
            retention_days=7,
            tenant_id=self.tenant.id,
            agent_id=self.agent.id,
        )

        camera = create_camera(data)

        assert camera.agent_id == self.agent.id
        assert Camera.objects.count() == 1

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_agent_mode_uses_publisher_source(self, mock_publish, mock_mtx_cls):
        """No modo agent, path é registrado com source='publisher'."""
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        data = CameraCreateInput(
            name="Cam Agent",
            location="Filial SP",
            rtsp_url="rtsp://192.168.1.100:554/stream",
            manufacturer="intelbras",
            retention_days=7,
            tenant_id=self.tenant.id,
            agent_id=self.agent.id,
        )

        camera = create_camera(data)

        mock_client.add_path.assert_called_once_with(
            name=f"tenant-{self.tenant.id}/cam-{camera.id}",
        )

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_pull_mode_uses_rtsp_source(self, mock_publish, mock_mtx_cls):
        """Sem agent, path é registrado com source=rtsp_url (pull mode)."""
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        data = CameraCreateInput(
            name="Cam Pull",
            location="Local",
            rtsp_url="rtsp://192.168.1.100:554/stream",
            manufacturer="intelbras",
            retention_days=7,
            tenant_id=self.tenant.id,
            agent_id=None,
        )

        camera = create_camera(data)

        mock_client.add_path.assert_called_once_with(
            name=f"tenant-{self.tenant.id}/cam-{camera.id}",
            source="rtsp://192.168.1.100:554/stream",
        )

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_camera_without_agent_has_null_agent(self, mock_publish, mock_mtx_cls):
        """Câmera sem agent tem agent_id=None."""
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        data = CameraCreateInput(
            name="Cam Pull",
            location="Local",
            rtsp_url="rtsp://192.168.1.100:554/stream",
            manufacturer="intelbras",
            retention_days=7,
            tenant_id=self.tenant.id,
        )

        camera = create_camera(data)

        assert camera.agent_id is None
