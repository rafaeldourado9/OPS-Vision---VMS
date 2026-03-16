"""Testes unitários para services de agents."""
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.agents.models import Agent
from apps.agents.services import (
    HeartbeatInput,
    create_agent,
    get_agent_config,
    process_heartbeat,
    revoke_agent,
)
from tests.factories import AgentFactory, CameraFactory, TenantFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestCreateAgent:
    """Testes do serviço de criação de agent."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.tenant = TenantFactory()

    @patch("apps.agents.services.publish_event")
    def test_creates_agent_in_database(self, mock_publish):
        """Cria agent no banco de dados."""
        agent, raw_key = create_agent("Filial SP", self.tenant.id)

        assert Agent.objects.count() == 1
        assert agent.name == "Filial SP"
        assert agent.tenant_id == self.tenant.id
        assert agent.status == Agent.Status.PENDING

    @patch("apps.agents.services.publish_event")
    def test_returns_raw_api_key(self, mock_publish):
        """Retorna a raw API key para exibição."""
        agent, raw_key = create_agent("Filial SP", self.tenant.id)

        assert len(raw_key) > 30
        assert agent.api_key == raw_key

    @patch("apps.agents.services.publish_event")
    def test_api_key_is_unique_per_agent(self, mock_publish):
        """Cada agent tem uma API key única."""
        _, key1 = create_agent("Agent 1", self.tenant.id)
        _, key2 = create_agent("Agent 2", self.tenant.id)

        assert key1 != key2

    @patch("apps.agents.services.publish_event")
    def test_publishes_agent_created_event(self, mock_publish):
        """Publica evento agent.created."""
        agent, _ = create_agent("Filial SP", self.tenant.id)

        mock_publish.assert_called_once_with(
            "agent.created",
            {
                "agent_id": agent.id,
                "tenant_id": self.tenant.id,
                "name": "Filial SP",
            },
        )


@pytest.mark.unit
@pytest.mark.django_db
class TestGetAgentConfig:
    """Testes do serviço de configuração do agent."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.tenant = TenantFactory()
        self.agent = AgentFactory(tenant=self.tenant)

    def test_returns_empty_cameras_when_none_assigned(self):
        """Retorna lista vazia quando agent não tem câmeras."""
        config = get_agent_config(self.agent)

        assert config.agent_id == self.agent.id
        assert config.tenant_id == self.tenant.id
        assert config.cameras == []
        assert config.poll_interval_seconds == 30

    def test_returns_cameras_assigned_to_agent(self):
        """Retorna câmeras associadas ao agent."""
        cam = CameraFactory(tenant=self.tenant, agent=self.agent)

        config = get_agent_config(self.agent)

        assert len(config.cameras) == 1
        assert config.cameras[0].id == cam.id
        assert config.cameras[0].name == cam.name
        assert config.cameras[0].rtsp_url == cam.rtsp_url
        assert config.cameras[0].enabled is True

    def test_rtmp_push_url_format(self):
        """Push URL segue o formato esperado."""
        cam = CameraFactory(tenant=self.tenant, agent=self.agent)

        config = get_agent_config(self.agent)

        expected_suffix = f"/tenant-{self.tenant.id}/cam-{cam.id}"
        assert config.cameras[0].rtmp_push_url.endswith(expected_suffix)

    def test_excludes_cameras_from_other_agents(self):
        """Não retorna câmeras de outros agents."""
        other_agent = AgentFactory(tenant=self.tenant)
        CameraFactory(tenant=self.tenant, agent=other_agent)
        my_cam = CameraFactory(tenant=self.tenant, agent=self.agent)

        config = get_agent_config(self.agent)

        assert len(config.cameras) == 1
        assert config.cameras[0].id == my_cam.id


@pytest.mark.unit
@pytest.mark.django_db
class TestProcessHeartbeat:
    """Testes do serviço de heartbeat."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.tenant = TenantFactory()
        self.agent = AgentFactory(
            tenant=self.tenant,
            status=Agent.Status.PENDING,
        )

    def test_updates_last_heartbeat(self):
        """Atualiza timestamp do último heartbeat."""
        data = HeartbeatInput(version="1.0.0", uptime_seconds=120, cameras={})
        before = timezone.now()

        process_heartbeat(self.agent, data)

        self.agent.refresh_from_db()
        assert self.agent.last_heartbeat >= before

    def test_sets_status_online(self):
        """Muda status para online."""
        data = HeartbeatInput(version="1.0.0", uptime_seconds=120, cameras={})

        process_heartbeat(self.agent, data)

        self.agent.refresh_from_db()
        assert self.agent.status == Agent.Status.ONLINE

    def test_updates_version(self):
        """Atualiza versão do agent."""
        data = HeartbeatInput(version="2.1.0", uptime_seconds=300, cameras={})

        process_heartbeat(self.agent, data)

        self.agent.refresh_from_db()
        assert self.agent.version == "2.1.0"


@pytest.mark.unit
@pytest.mark.django_db
class TestRevokeAgent:
    """Testes do serviço de revogação de agent."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.tenant = TenantFactory()
        self.agent = AgentFactory(tenant=self.tenant)

    @patch("apps.agents.services.publish_event")
    def test_deletes_agent(self, mock_publish):
        """Deleta agent do banco."""
        agent_id = self.agent.id

        revoke_agent(agent_id, self.tenant.id)

        assert Agent.objects.filter(id=agent_id).count() == 0

    @patch("apps.agents.services.publish_event")
    def test_publishes_agent_revoked_event(self, mock_publish):
        """Publica evento agent.revoked."""
        agent_id = self.agent.id

        revoke_agent(agent_id, self.tenant.id)

        mock_publish.assert_called_once_with(
            "agent.revoked",
            {
                "agent_id": agent_id,
                "tenant_id": self.tenant.id,
            },
        )

    @patch("apps.agents.services.publish_event")
    def test_raises_for_wrong_tenant(self, mock_publish):
        """Erro quando tenant_id não bate."""
        other_tenant = TenantFactory()

        with pytest.raises(Agent.DoesNotExist):
            revoke_agent(self.agent.id, other_tenant.id)

    @patch("apps.agents.services.publish_event")
    def test_raises_for_nonexistent_agent(self, mock_publish):
        """Erro quando agent não existe."""
        with pytest.raises(Agent.DoesNotExist):
            revoke_agent(99999, self.tenant.id)
