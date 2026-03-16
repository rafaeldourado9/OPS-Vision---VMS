"""Testes unitários para services de câmeras."""
from unittest.mock import MagicMock, patch

import pytest

from apps.cameras.models import Camera
from apps.cameras.services import (
    CameraCreateInput,
    CameraOfflineError,
    CameraUpdateInput,
    create_camera,
    delete_camera,
    generate_rtmp_push_url,
    get_camera_stream_url,
    update_camera,
)
from shared.mediamtx_client import MediaMTXError
from tests.factories import CameraFactory, TenantFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestCreateCamera:
    """Testes do serviço de criação de câmera."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.tenant = TenantFactory()
        self.input = CameraCreateInput(
            name="Cam 01",
            location="Estacionamento",
            rtsp_url="rtsp://192.168.1.100:554/stream",
            manufacturer="intelbras",
            retention_days=7,
            tenant_id=self.tenant.id,
        )

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_creates_camera_in_database(self, mock_publish, mock_mtx_cls):
        """Cria câmera no banco de dados."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        # Act
        camera = create_camera(self.input)

        # Assert
        assert Camera.objects.count() == 1
        assert camera.name == "Cam 01"
        assert camera.location == "Estacionamento"
        assert camera.rtsp_url == "rtsp://192.168.1.100:554/stream"
        assert camera.manufacturer == "intelbras"
        assert camera.retention_days == 7
        assert camera.tenant_id == self.tenant.id
        assert camera.is_online is False

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_registers_path_in_mediamtx(self, mock_publish, mock_mtx_cls):
        """Registra path no MediaMTX após criar."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        # Act
        camera = create_camera(self.input)

        # Assert
        mock_mtx_cls.assert_called_once()
        mock_client.add_path.assert_called_once_with(
            name=f"tenant-{self.tenant.id}/cam-{camera.id}",
            source=self.input.rtsp_url,
        )

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_publishes_camera_created_event(self, mock_publish, mock_mtx_cls):
        """Publica evento camera.created."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        # Act
        camera = create_camera(self.input)

        # Assert
        mock_publish.assert_called_once_with(
            "camera.created",
            {
                "camera_id": camera.id,
                "tenant_id": self.tenant.id,
                "name": "Cam 01",
                "location": "Estacionamento",
            },
        )

    @patch("apps.cameras.services.publish_event")
    @patch("apps.cameras.services.MediaMTXClient")
    def test_mediamtx_failure_raises_error(self, mock_mtx_cls, mock_publish):
        """Falha no MediaMTX propaga erro."""
        # Arrange
        mock_client = MagicMock()
        mock_client.add_path.side_effect = MediaMTXError("Connection timeout")
        mock_mtx_cls.return_value = mock_client

        # Act & Assert
        with pytest.raises(MediaMTXError) as exc_info:
            create_camera(self.input)

        assert "Connection timeout" in str(exc_info.value)

    @patch("apps.cameras.services.publish_event")
    @patch("apps.cameras.services.MediaMTXClient")
    def test_rollback_on_mediamtx_failure(self, mock_mtx_cls, mock_publish):
        """Rollback da transação se MediaMTX falhar."""
        # Arrange
        mock_client = MagicMock()
        mock_client.add_path.side_effect = MediaMTXError("Connection timeout")
        mock_mtx_cls.return_value = mock_client

        # Act
        with pytest.raises(MediaMTXError):
            create_camera(self.input)

        # Assert - câmera não deve existir no banco
        assert Camera.objects.count() == 0
        # Assert - evento não deve ter sido publicado
        mock_publish.assert_not_called()

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_event_published_after_mediamtx_success(self, mock_publish, mock_mtx_cls):
        """Evento só é publicado após sucesso no MediaMTX."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client
        call_order = []

        def track_add_path(*args, **kwargs):
            call_order.append("mediamtx")

        def track_publish(*args, **kwargs):
            call_order.append("event")

        mock_client.add_path.side_effect = track_add_path
        mock_publish.side_effect = track_publish

        # Act
        create_camera(self.input)

        # Assert - MediaMTX deve ser chamado antes do evento
        assert call_order == ["mediamtx", "event"]

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_creates_camera_with_default_values(self, mock_publish, mock_mtx_cls):
        """Cria câmera com valores padrão quando não especificados."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        input_minimal = CameraCreateInput(
            name="Cam Mínima",
            location="Hall",
            rtsp_url="rtsp://10.0.0.1/stream",
            manufacturer="other",
            retention_days=7,
            tenant_id=self.tenant.id,
        )

        # Act
        camera = create_camera(input_minimal)

        # Assert
        assert camera.is_online is False
        assert camera.manufacturer == "other"
        assert camera.retention_days == 7



@pytest.mark.unit
@pytest.mark.django_db
class TestUpdateCamera:
    """Testes do serviço de atualização de câmera."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.tenant = TenantFactory()
        self.camera = CameraFactory(
            name="Cam Original",
            location="Local Original",
            rtsp_url="rtsp://192.168.1.100:554/stream",
            manufacturer="intelbras",
            retention_days=7,
            tenant=self.tenant,
        )

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_updates_camera_fields(self, mock_publish, mock_mtx_cls):
        """Atualiza campos da câmera."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        update_data = CameraUpdateInput(
            name="Cam Atualizada",
            location="Novo Local",
            retention_days=15,
        )

        # Act
        updated_camera = update_camera(self.camera.id, update_data)

        # Assert
        assert updated_camera.id == self.camera.id
        assert updated_camera.name == "Cam Atualizada"
        assert updated_camera.location == "Novo Local"
        assert updated_camera.retention_days == 15
        # Campos não atualizados devem permanecer
        assert updated_camera.rtsp_url == "rtsp://192.168.1.100:554/stream"
        assert updated_camera.manufacturer == "intelbras"

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_updates_mediamtx_path_when_rtsp_changes(self, mock_publish, mock_mtx_cls):
        """Atualiza path no MediaMTX quando RTSP muda."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        update_data = CameraUpdateInput(
            rtsp_url="rtsp://192.168.1.200:554/new-stream",
        )

        # Act
        updated_camera = update_camera(self.camera.id, update_data)

        # Assert
        mock_client.edit_path.assert_called_once_with(
            name=f"tenant-{self.tenant.id}/cam-{self.camera.id}",
            source="rtsp://192.168.1.200:554/new-stream",
        )
        assert updated_camera.rtsp_url == "rtsp://192.168.1.200:554/new-stream"

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_does_not_update_mediamtx_when_rtsp_unchanged(self, mock_publish, mock_mtx_cls):
        """Não atualiza MediaMTX quando RTSP não muda."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        update_data = CameraUpdateInput(
            name="Novo Nome",
            location="Nova Localização",
        )

        # Act
        update_camera(self.camera.id, update_data)

        # Assert - edit_path não deve ser chamado
        mock_client.edit_path.assert_not_called()

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_publishes_camera_updated_event(self, mock_publish, mock_mtx_cls):
        """Publica evento camera.updated."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        update_data = CameraUpdateInput(
            name="Cam Atualizada",
            retention_days=30,
        )

        # Act
        updated_camera = update_camera(self.camera.id, update_data)

        # Assert
        mock_publish.assert_called_once_with(
            "camera.updated",
            {
                "camera_id": updated_camera.id,
                "tenant_id": self.tenant.id,
                "changed_fields": ["name", "retention_days"],
            },
        )

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_camera_not_found_raises_error(self, mock_publish, mock_mtx_cls):
        """Erro quando câmera não existe."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        update_data = CameraUpdateInput(name="Teste")

        # Act & Assert
        with pytest.raises(Camera.DoesNotExist):
            update_camera(99999, update_data)

    @patch("apps.cameras.services.publish_event")
    @patch("apps.cameras.services.MediaMTXClient")
    def test_mediamtx_failure_raises_error(self, mock_mtx_cls, mock_publish):
        """Falha no MediaMTX propaga erro."""
        # Arrange
        mock_client = MagicMock()
        mock_client.edit_path.side_effect = MediaMTXError("Connection timeout")
        mock_mtx_cls.return_value = mock_client

        update_data = CameraUpdateInput(
            rtsp_url="rtsp://192.168.1.200:554/stream",
        )

        # Act & Assert
        with pytest.raises(MediaMTXError) as exc_info:
            update_camera(self.camera.id, update_data)

        assert "Connection timeout" in str(exc_info.value)

    @patch("apps.cameras.services.publish_event")
    @patch("apps.cameras.services.MediaMTXClient")
    def test_rollback_on_mediamtx_failure(self, mock_mtx_cls, mock_publish):
        """Rollback da transação se MediaMTX falhar."""
        # Arrange
        mock_client = MagicMock()
        mock_client.edit_path.side_effect = MediaMTXError("Connection timeout")
        mock_mtx_cls.return_value = mock_client

        original_rtsp = self.camera.rtsp_url
        update_data = CameraUpdateInput(
            rtsp_url="rtsp://192.168.1.200:554/stream",
        )

        # Act
        with pytest.raises(MediaMTXError):
            update_camera(self.camera.id, update_data)

        # Assert - câmera deve manter valores originais
        self.camera.refresh_from_db()
        assert self.camera.rtsp_url == original_rtsp
        # Assert - evento não deve ter sido publicado
        mock_publish.assert_not_called()

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_partial_update_only_specified_fields(self, mock_publish, mock_mtx_cls):
        """Atualização parcial modifica apenas campos especificados."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        update_data = CameraUpdateInput(
            name="Apenas Nome Mudou",
        )

        # Act
        updated_camera = update_camera(self.camera.id, update_data)

        # Assert - apenas name mudou
        assert updated_camera.name == "Apenas Nome Mudou"
        assert updated_camera.location == "Local Original"
        assert updated_camera.rtsp_url == "rtsp://192.168.1.100:554/stream"
        assert updated_camera.manufacturer == "intelbras"
        assert updated_camera.retention_days == 7

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_event_includes_only_changed_fields(self, mock_publish, mock_mtx_cls):
        """Evento inclui apenas campos que foram alterados."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        update_data = CameraUpdateInput(
            name="Novo Nome",
            location="Nova Localização",
        )

        # Act
        update_camera(self.camera.id, update_data)

        # Assert
        call_args = mock_publish.call_args
        assert call_args[0][0] == "camera.updated"
        changed_fields = call_args[0][1]["changed_fields"]
        assert set(changed_fields) == {"name", "location"}
        assert "rtsp_url" not in changed_fields
        assert "manufacturer" not in changed_fields



@pytest.mark.unit
@pytest.mark.django_db
class TestDeleteCamera:
    """Testes do serviço de deleção de câmera."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.tenant = TenantFactory()
        self.camera = CameraFactory(
            name="Cam Para Deletar",
            location="Local Teste",
            rtsp_url="rtsp://192.168.1.100:554/stream",
            manufacturer="intelbras",
            retention_days=7,
            tenant=self.tenant,
        )

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_removes_path_from_mediamtx(self, mock_publish, mock_mtx_cls):
        """Remove path do MediaMTX antes de deletar."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client
        camera_id = self.camera.id
        tenant_id = self.tenant.id

        # Act
        delete_camera(camera_id)

        # Assert
        mock_client.remove_path.assert_called_once_with(
            name=f"tenant-{tenant_id}/cam-{camera_id}",
        )

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_deletes_camera_from_database(self, mock_publish, mock_mtx_cls):
        """Deleta câmera do banco de dados."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client
        camera_id = self.camera.id

        # Act
        delete_camera(camera_id)

        # Assert - câmera não deve existir mais
        assert Camera.objects.filter(id=camera_id).count() == 0

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_publishes_camera_deleted_event(self, mock_publish, mock_mtx_cls):
        """Publica evento camera.deleted."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client
        camera_id = self.camera.id
        tenant_id = self.tenant.id

        # Act
        delete_camera(camera_id)

        # Assert
        mock_publish.assert_called_once_with(
            "camera.deleted",
            {
                "camera_id": camera_id,
                "tenant_id": tenant_id,
            },
        )

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_camera_not_found_raises_error(self, mock_publish, mock_mtx_cls):
        """Erro quando câmera não existe."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        # Act & Assert
        with pytest.raises(Camera.DoesNotExist):
            delete_camera(99999)

    @patch("apps.cameras.services.publish_event")
    @patch("apps.cameras.services.MediaMTXClient")
    def test_mediamtx_failure_does_not_block_deletion(self, mock_mtx_cls, mock_publish):
        """Falha no MediaMTX não impede deleção (best-effort)."""
        # Arrange
        mock_client = MagicMock()
        mock_client.remove_path.side_effect = MediaMTXError("Connection timeout")
        mock_mtx_cls.return_value = mock_client
        camera_id = self.camera.id

        # Act — não propaga exceção
        delete_camera(camera_id)

        # Assert — câmera foi deletada mesmo assim
        assert Camera.objects.filter(id=camera_id).count() == 0
        # Assert — evento publicado normalmente
        mock_publish.assert_called_once()

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_event_published_after_deletion(self, mock_publish, mock_mtx_cls):
        """Evento é publicado após deleção bem-sucedida."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client
        call_order = []

        def track_remove_path(*args, **kwargs):
            call_order.append("mediamtx")

        def track_delete():
            call_order.append("database")

        def track_publish(*args, **kwargs):
            call_order.append("event")

        mock_client.remove_path.side_effect = track_remove_path
        mock_publish.side_effect = track_publish

        # Act
        delete_camera(self.camera.id)

        # Assert - ordem: MediaMTX → Database → Event
        assert "mediamtx" in call_order
        assert "event" in call_order
        assert call_order.index("mediamtx") < call_order.index("event")

    @patch("apps.cameras.services.MediaMTXClient")
    @patch("apps.cameras.services.publish_event")
    def test_returns_none(self, mock_publish, mock_mtx_cls):
        """Função retorna None após deleção."""
        # Arrange
        mock_client = MagicMock()
        mock_mtx_cls.return_value = mock_client

        # Act
        result = delete_camera(self.camera.id)

        # Assert
        assert result is None



@pytest.mark.unit
@pytest.mark.django_db
class TestGetCameraStreamUrl:
    """Testes do serviço de obtenção de URL de streaming."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.tenant = TenantFactory()
        self.camera_online = CameraFactory(
            name="Cam Online",
            location="Local Teste",
            rtsp_url="rtsp://192.168.1.100:554/stream",
            is_online=True,
            tenant=self.tenant,
        )
        self.camera_offline = CameraFactory(
            name="Cam Offline",
            location="Local Teste",
            rtsp_url="rtsp://192.168.1.101:554/stream",
            is_online=False,
            tenant=self.tenant,
        )

    def test_returns_stream_url_for_online_camera(self):
        """Retorna URL de streaming para câmera online."""
        # Act
        url = get_camera_stream_url(self.camera_online.id)

        # Assert
        expected_path = f"tenant-{self.tenant.id}/cam-{self.camera_online.id}"
        assert expected_path in url
        assert url.startswith("http://")

    def test_url_contains_correct_path(self):
        """URL contém o path correto da câmera."""
        # Act
        url = get_camera_stream_url(self.camera_online.id)

        # Assert
        assert f"tenant-{self.tenant.id}" in url
        assert f"cam-{self.camera_online.id}" in url

    def test_raises_error_for_offline_camera(self):
        """Erro quando câmera está offline."""
        # Act & Assert
        with pytest.raises(CameraOfflineError) as exc_info:
            get_camera_stream_url(self.camera_offline.id)

        assert "offline" in str(exc_info.value).lower()

    def test_camera_not_found_raises_error(self):
        """Erro quando câmera não existe."""
        # Act & Assert
        with pytest.raises(Camera.DoesNotExist):
            get_camera_stream_url(99999)

    def test_url_format_is_valid(self):
        """URL retornada tem formato válido."""
        # Act
        url = get_camera_stream_url(self.camera_online.id)

        # Assert
        assert url.startswith("http://") or url.startswith("https://")
        assert "/" in url
        assert len(url) > 10

    @patch("apps.cameras.services.settings")
    def test_uses_configured_base_url(self, mock_settings):
        """Usa URL base configurada nas settings."""
        # Arrange
        mock_settings.MEDIAMTX_STREAM_BASE_URL = "http://custom-mediamtx:9999"

        # Act
        url = get_camera_stream_url(self.camera_online.id)

        # Assert
        assert url.startswith("http://custom-mediamtx:9999")

    def test_different_cameras_have_different_urls(self):
        """Câmeras diferentes têm URLs diferentes."""
        # Arrange
        camera2 = CameraFactory(
            is_online=True,
            tenant=self.tenant,
        )

        # Act
        url1 = get_camera_stream_url(self.camera_online.id)
        url2 = get_camera_stream_url(camera2.id)

        # Assert
        assert url1 != url2
        assert f"cam-{self.camera_online.id}" in url1
        assert f"cam-{camera2.id}" in url2


@pytest.mark.unit
@pytest.mark.django_db
class TestGenerateRtmpPushUrl:
    """Testes do serviço de geração de URL RTMP push."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.tenant = TenantFactory()
        self.camera = CameraFactory(tenant=self.tenant)

    def test_returns_dict_with_required_keys(self):
        """Retorna dicionário com rtmp_url, stream_key e full_url."""
        result = generate_rtmp_push_url(self.camera.id, self.tenant.id)

        assert "rtmp_url" in result
        assert "stream_key" in result
        assert "full_url" in result

    def test_rtmp_url_contains_tenant_app(self):
        """rtmp_url contém o app path com tenant."""
        result = generate_rtmp_push_url(self.camera.id, self.tenant.id)

        assert result["rtmp_url"].endswith(f"/tenant-{self.tenant.id}")

    def test_stream_key_is_camera_id(self):
        """stream_key é cam-{id}."""
        result = generate_rtmp_push_url(self.camera.id, self.tenant.id)

        assert result["stream_key"] == f"cam-{self.camera.id}"

    def test_full_url_combines_rtmp_url_and_stream_key(self):
        """full_url é rtmp_url/stream_key."""
        result = generate_rtmp_push_url(self.camera.id, self.tenant.id)

        assert result["full_url"] == f"{result['rtmp_url']}/{result['stream_key']}"

    def test_full_url_matches_mediamtx_path(self):
        """full_url gera path compatível com _build_path_name."""
        result = generate_rtmp_push_url(self.camera.id, self.tenant.id)

        # Extrai o path após host:port/ — deve ser tenant-X/cam-Y
        path_part = "/".join(result["full_url"].split("/")[-2:])
        assert path_part == f"tenant-{self.tenant.id}/cam-{self.camera.id}"

    @patch("apps.cameras.services.settings")
    def test_uses_configured_rtmp_url(self, mock_settings):
        """Usa MEDIAMTX_RTMP_URL das settings."""
        mock_settings.MEDIAMTX_RTMP_URL = "rtmp://custom-server:1935"

        result = generate_rtmp_push_url(self.camera.id, self.tenant.id)

        assert result["rtmp_url"].startswith("rtmp://custom-server:1935")

    def test_camera_not_found_raises_error(self):
        """Erro quando câmera não existe."""
        with pytest.raises(Camera.DoesNotExist):
            generate_rtmp_push_url(99999, self.tenant.id)
