"""Testes unitários para views de agents."""
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.agents.models import Agent
from tests.factories import AgentFactory, CameraFactory, TenantFactory, UserFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestAgentViewSetList:
    """Testes do endpoint GET /api/v1/agents/."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.client = APIClient()
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.client.force_authenticate(user=self.user)

    def test_lists_only_tenant_agents(self):
        """Lista somente agents do tenant do usuário."""
        my_agent = AgentFactory(tenant=self.tenant)
        AgentFactory()  # outro tenant

        response = self.client.get("/api/v1/agents/")

        assert response.status_code == status.HTTP_200_OK
        ids = [a["id"] for a in response.data]
        assert my_agent.id in ids
        assert len(ids) == 1

    def test_requires_authentication(self):
        """Requer autenticação."""
        client = APIClient()
        response = client.get("/api/v1/agents/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.unit
@pytest.mark.django_db
class TestAgentViewSetCreate:
    """Testes do endpoint POST /api/v1/agents/."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.client = APIClient()
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.client.force_authenticate(user=self.user)

    @patch("apps.agents.services.publish_event")
    def test_creates_agent_returns_201(self, mock_publish):
        """Cria agent e retorna 201 com api_key."""
        response = self.client.post("/api/v1/agents/", {"name": "Filial SP"})

        assert response.status_code == status.HTTP_201_CREATED
        assert "api_key" in response.data
        assert response.data["name"] == "Filial SP"
        assert len(response.data["api_key"]) > 30

    @patch("apps.agents.services.publish_event")
    def test_agent_belongs_to_user_tenant(self, mock_publish):
        """Agent criado pertence ao tenant do usuário."""
        self.client.post("/api/v1/agents/", {"name": "Filial SP"})

        agent = Agent.objects.first()
        assert agent.tenant_id == self.tenant.id

    def test_validation_error_without_name(self):
        """Erro de validação sem nome."""
        response = self.client.post("/api/v1/agents/", {})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.unit
@pytest.mark.django_db
class TestAgentViewSetDestroy:
    """Testes do endpoint DELETE /api/v1/agents/{id}/."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.client = APIClient()
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.client.force_authenticate(user=self.user)

    @patch("apps.agents.services.publish_event")
    def test_deletes_agent_returns_204(self, mock_publish):
        """Deleta agent e retorna 204."""
        agent = AgentFactory(tenant=self.tenant)

        response = self.client.delete(f"/api/v1/agents/{agent.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Agent.objects.filter(id=agent.id).count() == 0

    @patch("apps.agents.services.publish_event")
    def test_cannot_delete_other_tenant_agent(self, mock_publish):
        """Não pode deletar agent de outro tenant."""
        other_agent = AgentFactory()

        response = self.client.delete(f"/api/v1/agents/{other_agent.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_404_for_nonexistent(self):
        """Retorna 404 para agent inexistente."""
        response = self.client.delete("/api/v1/agents/99999/")

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.unit
@pytest.mark.django_db
class TestAgentMeView:
    """Testes do endpoint GET /api/v1/agents/me/."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.client = APIClient()
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.agent = AgentFactory(tenant=self.tenant)

    def test_returns_agent_info(self):
        """Retorna info do agent autenticado."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Agent {self.agent.api_key}"
        )

        response = self.client.get("/api/v1/agents/me/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == self.agent.id
        assert response.data["name"] == self.agent.name

    def test_rejects_invalid_key(self):
        """Rejeita API key inválida."""
        self.client.credentials(
            HTTP_AUTHORIZATION="Agent invalid-key"
        )

        response = self.client.get("/api/v1/agents/me/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.unit
@pytest.mark.django_db
class TestAgentConfigView:
    """Testes do endpoint GET /api/v1/agents/me/config/."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.client = APIClient()
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.agent = AgentFactory(tenant=self.tenant)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Agent {self.agent.api_key}"
        )

    def test_returns_config_with_cameras(self):
        """Retorna configuração com câmeras do agent."""
        cam = CameraFactory(tenant=self.tenant, agent=self.agent)

        response = self.client.get("/api/v1/agents/me/config/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["agent_id"] == self.agent.id
        assert len(response.data["cameras"]) == 1
        assert response.data["cameras"][0]["id"] == cam.id
        assert "rtmp_push_url" in response.data["cameras"][0]

    def test_returns_empty_cameras_initially(self):
        """Retorna lista vazia quando sem câmeras."""
        response = self.client.get("/api/v1/agents/me/config/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["cameras"] == []


@pytest.mark.unit
@pytest.mark.django_db
class TestAgentHeartbeatView:
    """Testes do endpoint POST /api/v1/agents/me/heartbeat/."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.client = APIClient()
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.agent = AgentFactory(tenant=self.tenant)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Agent {self.agent.api_key}"
        )

    def test_heartbeat_updates_agent(self):
        """Heartbeat atualiza status do agent."""
        response = self.client.post(
            "/api/v1/agents/me/heartbeat/",
            {"version": "1.0.0", "uptime_seconds": 120, "cameras": {}},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        self.agent.refresh_from_db()
        assert self.agent.status == "online"
        assert self.agent.version == "1.0.0"
        assert self.agent.last_heartbeat is not None

    def test_validation_error_without_version(self):
        """Erro de validação sem versão."""
        response = self.client.post(
            "/api/v1/agents/me/heartbeat/",
            {"uptime_seconds": 120},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
