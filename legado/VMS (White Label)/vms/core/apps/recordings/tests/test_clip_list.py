"""Testes para ClipListView GET /api/v1/recordings/clips/."""
import pytest
from django.utils import timezone

from apps.recordings.models import Clip
from tests.factories import CameraFactory, TenantFactory, UserFactory


def _make_clip(camera, status=Clip.Status.READY, file_path="/tmp/test.mp4"):
    """Helper para criar um Clip."""
    now = timezone.now()
    return Clip.objects.create(
        tenant=camera.tenant,
        camera=camera,
        start_time=now,
        end_time=now,
        status=status,
        file_path=file_path,
    )


@pytest.mark.unit
@pytest.mark.django_db
class TestClipListView:
    """Testes de GET /api/v1/recordings/clips/."""

    def test_list_returns_own_tenant_clips(self, authenticated_client, user):
        """Lista apenas clips do tenant autenticado."""
        camera = CameraFactory(tenant=user.tenant)
        clip = _make_clip(camera)

        # Clip de outro tenant — não deve aparecer
        other_camera = CameraFactory()
        _make_clip(other_camera)

        response = authenticated_client.get("/api/v1/recordings/clips/")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["id"] == clip.id

    def test_response_includes_required_fields(self, authenticated_client, user):
        """Resposta contém todos os campos que o frontend espera."""
        camera = CameraFactory(tenant=user.tenant)
        clip = _make_clip(camera)

        response = authenticated_client.get("/api/v1/recordings/clips/")

        result = response.json()["results"][0]
        assert "id" in result
        assert "status" in result
        assert "camera_id" in result
        assert "camera_name" in result
        assert "started_at" in result
        assert "ended_at" in result
        assert "file_size_bytes" in result
        assert "created_at" in result

    def test_camera_name_is_correct(self, authenticated_client, user):
        """Campo camera_name reflete o nome da câmera."""
        camera = CameraFactory(tenant=user.tenant, name="Entrada Principal")
        _make_clip(camera)

        response = authenticated_client.get("/api/v1/recordings/clips/")

        result = response.json()["results"][0]
        assert result["camera_name"] == "Entrada Principal"

    def test_is_paginated(self, authenticated_client, user):
        """Resposta é paginada com count, next e previous."""
        camera = CameraFactory(tenant=user.tenant)
        for _ in range(3):
            _make_clip(camera)

        response = authenticated_client.get("/api/v1/recordings/clips/")

        data = response.json()
        assert "count" in data
        assert "next" in data
        assert "previous" in data
        assert data["count"] == 3

    def test_requires_authentication(self, api_client):
        """Retorna 401 para request sem token."""
        response = api_client.get("/api/v1/recordings/clips/")

        assert response.status_code == 401

    def test_empty_list_for_new_tenant(self, authenticated_client):
        """Novo tenant sem clips retorna lista vazia."""
        response = authenticated_client.get("/api/v1/recordings/clips/")

        data = response.json()
        assert data["count"] == 0
        assert data["results"] == []
