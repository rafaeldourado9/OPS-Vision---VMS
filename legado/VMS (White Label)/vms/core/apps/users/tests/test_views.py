"""Testes para a view /auth/me/."""
import pytest
from rest_framework.test import APIClient

from tests.factories import TenantFactory, UserFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestUserMeView:
    """Testes do endpoint GET /api/v1/auth/me/."""

    def test_returns_current_user(self, authenticated_client, user):
        """Retorna dados do usuário autenticado."""
        response = authenticated_client.get("/api/v1/auth/me/")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user.id
        assert data["username"] == user.username
        assert data["email"] == user.email

    def test_includes_tenant_info(self, authenticated_client, user):
        """Resposta inclui id e nome do tenant."""
        response = authenticated_client.get("/api/v1/auth/me/")

        assert response.status_code == 200
        tenant = response.json()["tenant"]
        assert tenant["id"] == user.tenant.id
        assert tenant["name"] == user.tenant.name
        assert tenant["slug"] == user.tenant.slug

    def test_requires_authentication(self, api_client):
        """Retorna 401 para request sem token."""
        response = api_client.get("/api/v1/auth/me/")

        assert response.status_code == 401

    def test_different_users_see_own_data(self, api_client):
        """Cada usuário vê apenas seus próprios dados."""
        user_a = UserFactory()
        user_b = UserFactory()

        api_client.force_authenticate(user=user_a)
        response_a = api_client.get("/api/v1/auth/me/")
        assert response_a.json()["username"] == user_a.username

        api_client.force_authenticate(user=user_b)
        response_b = api_client.get("/api/v1/auth/me/")
        assert response_b.json()["username"] == user_b.username
