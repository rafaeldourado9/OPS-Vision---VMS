"""Testes unitários para autenticação de agents."""
import pytest
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from apps.agents.authentication import AgentAuthentication
from tests.factories import AgentFactory, TenantFactory, UserFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestAgentAuthentication:
    """Testes do AgentAuthentication."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.auth = AgentAuthentication()
        self.factory = APIRequestFactory()
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.agent = AgentFactory(tenant=self.tenant)

    def test_authenticates_valid_agent_key(self):
        """Autentica agent com API key válida."""
        request = self.factory.get(
            "/", HTTP_AUTHORIZATION=f"Agent {self.agent.api_key}"
        )
        user, auth_info = self.auth.authenticate(request)

        assert user == self.user
        assert auth_info == self.agent
        assert request.agent == self.agent

    def test_returns_none_for_missing_header(self):
        """Retorna None se header Authorization ausente."""
        request = self.factory.get("/")
        result = self.auth.authenticate(request)

        assert result is None

    def test_returns_none_for_non_agent_scheme(self):
        """Retorna None se scheme não é Agent."""
        request = self.factory.get(
            "/", HTTP_AUTHORIZATION="Bearer some-jwt-token"
        )
        result = self.auth.authenticate(request)

        assert result is None

    def test_raises_for_invalid_key(self):
        """Erro 401 para API key inválida."""
        request = self.factory.get(
            "/", HTTP_AUTHORIZATION="Agent invalid-key-here"
        )

        with pytest.raises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_raises_for_tenant_without_users(self):
        """Erro 401 se tenant do agent não tem usuários."""
        empty_tenant = TenantFactory()
        agent = AgentFactory(tenant=empty_tenant)
        request = self.factory.get(
            "/", HTTP_AUTHORIZATION=f"Agent {agent.api_key}"
        )

        with pytest.raises(AuthenticationFailed, match="não possui usuários"):
            self.auth.authenticate(request)

    def test_authenticate_header_returns_keyword(self):
        """authenticate_header retorna 'Agent'."""
        request = self.factory.get("/")
        assert self.auth.authenticate_header(request) == "Agent"
