"""Views para agents."""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import AgentAuthentication
from .models import Agent
from .serializers import (
    AgentConfigResponseSerializer,
    AgentCreateResponseSerializer,
    AgentCreateSerializer,
    AgentSerializer,
    HeartbeatSerializer,
)
from .services import (
    HeartbeatInput,
    create_agent,
    get_agent_config,
    process_heartbeat,
    revoke_agent,
)


class AgentViewSet(viewsets.ViewSet):
    """ViewSet para admin gerenciar agents (JWT auth)."""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Lista agents do tenant."""
        agents = Agent.objects.filter(tenant=request.user.tenant)
        serializer = AgentSerializer(agents, many=True)
        return Response(serializer.data)

    def create(self, request):
        """Cria um agent e retorna a api_key (exibida uma única vez)."""
        serializer = AgentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        agent, raw_key = create_agent(
            name=serializer.validated_data["name"],
            tenant_id=request.user.tenant_id,
        )

        response_data = {
            "id": agent.id,
            "name": agent.name,
            "api_key": raw_key,
            "status": agent.status,
            "created_at": agent.created_at,
        }
        return Response(
            AgentCreateResponseSerializer(response_data).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, pk=None):
        """Revoga (deleta) um agent."""
        try:
            revoke_agent(
                agent_id=int(pk),
                tenant_id=request.user.tenant_id,
            )
        except Agent.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_204_NO_CONTENT)


class AgentMeView(APIView):
    """Endpoint para agent consultar seus próprios dados."""

    authentication_classes = [AgentAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Retorna info do agent autenticado."""
        agent = request.agent
        return Response(AgentSerializer(agent).data)


class AgentConfigView(APIView):
    """Endpoint para agent obter sua configuração desejada."""

    authentication_classes = [AgentAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Retorna configuração (câmeras + push URLs) para o agent."""
        agent = request.agent
        config = get_agent_config(agent)
        serializer = AgentConfigResponseSerializer(config)
        return Response(serializer.data)


class AgentHeartbeatView(APIView):
    """Endpoint para agent reportar saúde."""

    authentication_classes = [AgentAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Recebe heartbeat do agent."""
        serializer = HeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        process_heartbeat(
            agent=request.agent,
            data=HeartbeatInput(**serializer.validated_data),
        )

        return Response({"status": "ok"})
