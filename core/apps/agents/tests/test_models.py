"""Testes unitários para models de agents."""
import pytest

from apps.agents.models import Agent
from tests.factories import AgentFactory, TenantFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestAgentModel:
    """Testes do model Agent."""

    def test_create_agent_with_defaults(self):
        """Agent criado com valores padrão."""
        agent = AgentFactory()

        assert agent.status == Agent.Status.PENDING
        assert agent.last_heartbeat is None
        assert agent.version == ""
        assert agent.metadata == {}

    def test_agent_str_representation(self):
        """__str__ retorna nome e status."""
        agent = AgentFactory(name="Filial SP")

        assert "Filial SP" in str(agent)
        assert "Pendente" in str(agent)

    def test_agent_belongs_to_tenant(self):
        """Agent pertence a um tenant."""
        tenant = TenantFactory()
        agent = AgentFactory(tenant=tenant)

        assert agent.tenant == tenant
        assert agent in tenant.agents.all()

    def test_api_key_is_unique(self):
        """api_key tem constraint unique."""
        agent1 = AgentFactory()
        with pytest.raises(Exception):
            AgentFactory(api_key=agent1.api_key)

    def test_status_choices(self):
        """Status aceita valores válidos."""
        agent = AgentFactory(status=Agent.Status.ONLINE)
        assert agent.status == "online"

        agent.status = Agent.Status.OFFLINE
        agent.save()
        agent.refresh_from_db()
        assert agent.status == "offline"
