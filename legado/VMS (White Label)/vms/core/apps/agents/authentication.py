"""Autenticação por API key para agents."""
from rest_framework import authentication, exceptions

from .models import Agent


class AgentAuthentication(authentication.BaseAuthentication):
    """Autentica requests de agents via header ``Authorization: Agent <api_key>``.

    Seta ``request.agent`` com a instância do Agent e
    ``request.user`` como o primeiro admin do tenant (para compatibilidade DRF).
    """

    keyword = "Agent"

    def authenticate(self, request):
        """Extrai e valida a API key do header Authorization.

        Returns:
            Tupla (user, agent) ou None se header ausente.

        Raises:
            AuthenticationFailed: API key inválida.
        """
        auth_header = authentication.get_authorization_header(request)
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2:
            return None

        keyword = parts[0].decode("utf-8")
        if keyword != self.keyword:
            return None

        api_key = parts[1].decode("utf-8")
        return self._authenticate_key(api_key, request)

    def _authenticate_key(self, api_key: str, request):
        """Valida a API key e retorna (user, agent).

        Args:
            api_key: Chave de API do agent.
            request: Request HTTP.

        Returns:
            Tupla (user, agent).

        Raises:
            AuthenticationFailed: API key inválida.
        """
        try:
            agent = Agent.objects.select_related("tenant").get(api_key=api_key)
        except Agent.DoesNotExist:
            raise exceptions.AuthenticationFailed("API key inválida.")

        # Resolve um user do tenant para compatibilidade com DRF permissions
        user = agent.tenant.users.first()
        if user is None:
            raise exceptions.AuthenticationFailed(
                "Tenant do agent não possui usuários."
            )

        # Seta agent no request para uso nos views
        request.agent = agent
        return (user, agent)

    def authenticate_header(self, request):
        """Retorna header WWW-Authenticate para 401."""
        return self.keyword
