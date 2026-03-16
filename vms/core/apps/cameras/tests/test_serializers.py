"""Testes unitários para serializers de câmeras."""
import pytest

from apps.cameras.models import Camera
from apps.cameras.serializers import (
    CameraCreateSerializer,
    CameraSerializer,
    CameraUpdateSerializer,
)
from tests.factories import CameraFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestCameraSerializer:
    """Testes do CameraSerializer."""

    def test_serializes_camera_correctly(self):
        """Serializa câmera com todos os campos."""
        # Arrange
        camera = CameraFactory()

        # Act
        serializer = CameraSerializer(camera)

        # Assert
        assert serializer.data["id"] == camera.id
        assert serializer.data["name"] == camera.name
        assert serializer.data["location"] == camera.location
        assert serializer.data["rtsp_url"] == camera.rtsp_url
        assert serializer.data["manufacturer"] == camera.manufacturer
        assert serializer.data["retention_days"] == camera.retention_days
        assert serializer.data["is_online"] == camera.is_online
        assert "created_at" in serializer.data
        assert "updated_at" in serializer.data

    def test_read_only_fields_cannot_be_updated(self):
        """Campos read-only não podem ser atualizados."""
        # Arrange
        camera = CameraFactory(is_online=False)
        original_tenant_id = camera.tenant_id
        data = {
            "name": "Novo Nome",
            "is_online": True,  # read-only — deve ser ignorado
            "tenant": 999,  # read-only — deve ser ignorado
        }

        # Act
        serializer = CameraSerializer(camera, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Assert
        camera.refresh_from_db()
        assert camera.name == "Novo Nome"
        assert camera.is_online is False  # Não mudou
        assert camera.tenant_id == original_tenant_id  # Não mudou


@pytest.mark.unit
class TestCameraCreateSerializer:
    """Testes do CameraCreateSerializer."""

    def test_validates_required_fields(self):
        """Valida campos obrigatórios."""
        # Arrange
        data = {}

        # Act
        serializer = CameraCreateSerializer(data=data)

        # Assert
        assert not serializer.is_valid()
        assert "name" in serializer.errors
        assert "location" in serializer.errors
        assert "rtsp_url" in serializer.errors

    def test_accepts_valid_data(self):
        """Aceita dados válidos."""
        # Arrange
        data = {
            "name": "Cam 01",
            "location": "Portaria",
            "rtsp_url": "rtsp://192.168.1.100:554/stream",
            "manufacturer": "intelbras",
            "retention_days": 7,
        }

        # Act
        serializer = CameraCreateSerializer(data=data)

        # Assert
        assert serializer.is_valid()
        assert serializer.validated_data["name"] == "Cam 01"

    def test_uses_default_values(self):
        """Usa valores padrão quando não especificados."""
        # Arrange
        data = {
            "name": "Cam 01",
            "location": "Portaria",
            "rtsp_url": "rtsp://192.168.1.100:554/stream",
        }

        # Act
        serializer = CameraCreateSerializer(data=data)

        # Assert
        assert serializer.is_valid()
        assert serializer.validated_data["manufacturer"] == Camera.Manufacturer.OTHER
        assert serializer.validated_data["retention_days"] == Camera.RetentionDays.SEVEN

    def test_validates_rtsp_url_format(self):
        """Valida formato da URL RTSP."""
        # Arrange
        data = {
            "name": "Cam 01",
            "location": "Portaria",
            "rtsp_url": "invalid-url",
        }

        # Act
        serializer = CameraCreateSerializer(data=data)

        # Assert
        assert not serializer.is_valid()
        assert "rtsp_url" in serializer.errors

    def test_validates_manufacturer_choices(self):
        """Valida choices de manufacturer."""
        # Arrange
        data = {
            "name": "Cam 01",
            "location": "Portaria",
            "rtsp_url": "rtsp://192.168.1.100:554/stream",
            "manufacturer": "invalid_manufacturer",
        }

        # Act
        serializer = CameraCreateSerializer(data=data)

        # Assert
        assert not serializer.is_valid()
        assert "manufacturer" in serializer.errors

    def test_validates_retention_days_choices(self):
        """Valida choices de retention_days."""
        # Arrange
        data = {
            "name": "Cam 01",
            "location": "Portaria",
            "rtsp_url": "rtsp://192.168.1.100:554/stream",
            "retention_days": 999,
        }

        # Act
        serializer = CameraCreateSerializer(data=data)

        # Assert
        assert not serializer.is_valid()
        assert "retention_days" in serializer.errors


@pytest.mark.unit
class TestCameraUpdateSerializer:
    """Testes do CameraUpdateSerializer."""

    def test_all_fields_are_optional(self):
        """Todos os campos são opcionais."""
        # Arrange
        data = {}

        # Act
        serializer = CameraUpdateSerializer(data=data)

        # Assert
        assert serializer.is_valid()

    def test_accepts_partial_update(self):
        """Aceita atualização parcial."""
        # Arrange
        data = {"name": "Novo Nome"}

        # Act
        serializer = CameraUpdateSerializer(data=data)

        # Assert
        assert serializer.is_valid()
        assert serializer.validated_data["name"] == "Novo Nome"
        assert "location" not in serializer.validated_data

    def test_validates_rtsp_url_format_when_provided(self):
        """Valida formato da URL RTSP quando fornecida."""
        # Arrange
        data = {"rtsp_url": "invalid-url"}

        # Act
        serializer = CameraUpdateSerializer(data=data)

        # Assert
        assert not serializer.is_valid()
        assert "rtsp_url" in serializer.errors

    def test_validates_manufacturer_choices_when_provided(self):
        """Valida choices de manufacturer quando fornecido."""
        # Arrange
        data = {"manufacturer": "invalid_manufacturer"}

        # Act
        serializer = CameraUpdateSerializer(data=data)

        # Assert
        assert not serializer.is_valid()
        assert "manufacturer" in serializer.errors

    def test_accepts_multiple_fields(self):
        """Aceita múltiplos campos."""
        # Arrange
        data = {
            "name": "Novo Nome",
            "location": "Nova Localização",
            "retention_days": 30,
        }

        # Act
        serializer = CameraUpdateSerializer(data=data)

        # Assert
        assert serializer.is_valid()
        assert len(serializer.validated_data) == 3
