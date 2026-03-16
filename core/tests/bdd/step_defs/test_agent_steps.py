"""Step definitions para gerenciamento de agents."""
from unittest.mock import patch

import pytest
from pytest_bdd import given, parsers, scenario, then, when
from rest_framework import status
from rest_framework.test import APIClient

from apps.agents.models import Agent
from tests.factories import AgentFactory, CameraFactory, TenantFactory, UserFactory

pytestmark = [pytest.mark.bdd, pytest.mark.django_db]


# Scenarios
@scenario("../features/agent_management.feature", "Criar agent com sucesso")
def test_create_agent():
    pass


@scenario("../features/agent_management.feature", "Listar agents do meu tenant")
def test_list_agents():
    pass


@scenario("../features/agent_management.feature", "Revogar agent")
def test_revoke_agent():
    pass


@scenario(
    "../features/agent_management.feature",
    "Agent consulta seus próprios dados",
)
def test_agent_me():
    pass


@scenario(
    "../features/agent_management.feature",
    "Agent obtém configuração",
)
def test_agent_config():
    pass


@scenario(
    "../features/agent_management.feature",
    "Agent envia heartbeat",
)
def test_agent_heartbeat():
    pass


# Given steps
@given("que estou autenticado como admin de agents", target_fixture="ctx")
def authenticated_admin():
    """Cria admin autenticado via JWT."""
    client = APIClient()
    user = UserFactory()
    client.force_authenticate(user=user)
    return {
        "client": client,
        "user": user,
        "tenant": user.tenant,
        "response": None,
        "agent": None,
        "agent_client": None,
    }


@given(parsers.parse("que existem {count:d} agents no meu tenant"))
def agents_in_my_tenant(ctx, count):
    """Cria agents no tenant do usuário."""
    for _ in range(count):
        AgentFactory(tenant=ctx["tenant"])


@given(parsers.parse("existem {count:d} agents em outro tenant"))
def agents_in_other_tenant(ctx, count):
    """Cria agents em outro tenant."""
    other = TenantFactory()
    for _ in range(count):
        AgentFactory(tenant=other)


@given(parsers.parse('que existe um agent "{name}"'))
def agent_exists(ctx, name):
    """Cria agent com nome específico."""
    ctx["agent"] = AgentFactory(name=name, tenant=ctx["tenant"])


@given(parsers.parse('que existe um agent autenticado "{name}"'))
def authenticated_agent(ctx, name):
    """Cria agent e client autenticado com API key."""
    agent = AgentFactory(name=name, tenant=ctx["tenant"])
    ctx["agent"] = agent

    agent_client = APIClient()
    agent_client.credentials(HTTP_AUTHORIZATION=f"Agent {agent.api_key}")
    ctx["agent_client"] = agent_client


@given(parsers.parse("o agent tem {count:d} câmeras atribuídas"))
def cameras_assigned_to_agent(ctx, count):
    """Cria câmeras atribuídas ao agent."""
    for _ in range(count):
        CameraFactory(tenant=ctx["tenant"], agent=ctx["agent"])


# When steps
@when(parsers.parse('eu crio um agent com nome "{name}"'))
def create_agent(ctx, name):
    """Cria agent via API."""
    with patch("apps.agents.services.publish_event"):
        ctx["response"] = ctx["client"].post(
            "/api/v1/agents/",
            {"name": name},
            format="json",
        )


@when("eu listo os agents")
def list_agents(ctx):
    """Lista agents."""
    ctx["response"] = ctx["client"].get("/api/v1/agents/")


@when("eu revogo o agent")
def revoke_agent_step(ctx):
    """Revoga agent."""
    ctx["agent_id"] = ctx["agent"].id
    with patch("apps.agents.services.publish_event"):
        ctx["response"] = ctx["client"].delete(
            f"/api/v1/agents/{ctx['agent'].id}/"
        )


@when("o agent consulta /agents/me/")
def agent_me(ctx):
    """Agent consulta seus dados."""
    ctx["response"] = ctx["agent_client"].get("/api/v1/agents/me/")


@when("o agent consulta /agents/me/config/")
def agent_config(ctx):
    """Agent consulta configuração."""
    ctx["response"] = ctx["agent_client"].get("/api/v1/agents/me/config/")


@when(parsers.parse('o agent envia heartbeat com versão "{version}"'))
def agent_heartbeat(ctx, version):
    """Agent envia heartbeat."""
    ctx["response"] = ctx["agent_client"].post(
        "/api/v1/agents/me/heartbeat/",
        {
            "version": version,
            "uptime_seconds": 3600,
            "cameras": {},
        },
        format="json",
    )


# Then steps
@then("o agent é criado com sucesso")
def agent_created(ctx):
    """Verifica criação."""
    assert ctx["response"].status_code == status.HTTP_201_CREATED
    assert "id" in ctx["response"].data


@then("a resposta contém a api_key")
def response_has_api_key(ctx):
    """Verifica que api_key foi retornada."""
    assert "api_key" in ctx["response"].data
    assert len(ctx["response"].data["api_key"]) > 0


@then(parsers.parse('o agent tem status "{expected_status}"'))
def agent_has_status(ctx, expected_status):
    """Verifica status do agent."""
    assert ctx["response"].data["status"] == expected_status


@then(parsers.parse("vejo {count:d} agents na lista"))
def see_agent_count(ctx, count):
    """Verifica quantidade de agents."""
    data = ctx["response"].data
    results = data.get("results", data) if isinstance(data, dict) else data
    assert len(results) == count


@then("não vejo agents de outros tenants")
def no_other_tenant_agents(ctx):
    """Verifica isolamento de tenants."""
    data = ctx["response"].data
    results = data.get("results", data) if isinstance(data, dict) else data
    for agent_data in results:
        agent = Agent.objects.get(id=agent_data["id"])
        assert agent.tenant == ctx["tenant"]


@then("o agent é removido com sucesso")
def agent_deleted(ctx):
    """Verifica remoção."""
    assert ctx["response"].status_code == status.HTTP_204_NO_CONTENT


@then("o agent não aparece mais na lista")
def agent_not_in_list(ctx):
    """Verifica que agent foi removido."""
    assert not Agent.objects.filter(id=ctx["agent_id"]).exists()


@then("vejo os dados do agent")
def see_agent_data(ctx):
    """Verifica dados do agent."""
    assert ctx["response"].status_code == status.HTTP_200_OK
    assert "id" in ctx["response"].data
    assert "name" in ctx["response"].data


@then(parsers.parse('o nome é "{name}"'))
def agent_name_is(ctx, name):
    """Verifica nome do agent."""
    assert ctx["response"].data["name"] == name


@then(parsers.parse("a configuração contém {count:d} câmeras"))
def config_has_cameras(ctx, count):
    """Verifica câmeras na configuração."""
    assert ctx["response"].status_code == status.HTTP_200_OK
    assert len(ctx["response"].data["cameras"]) == count


@then("cada câmera tem push URL RTMP")
def cameras_have_rtmp(ctx):
    """Verifica push URL em cada câmera."""
    for cam in ctx["response"].data["cameras"]:
        assert "rtmp_push_url" in cam
        assert cam["rtmp_push_url"].startswith("rtmp://")


@then("o heartbeat é aceito")
def heartbeat_accepted(ctx):
    """Verifica heartbeat aceito."""
    assert ctx["response"].status_code == status.HTTP_200_OK


@then(parsers.parse('o status do agent muda para "{expected_status}"'))
def agent_status_changed(ctx, expected_status):
    """Verifica mudança de status."""
    ctx["agent"].refresh_from_db()
    assert ctx["agent"].status == expected_status
