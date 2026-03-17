"""Services de domínio para agents."""
import secrets
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from shared.event_bus import publish_event

from .models import Agent


@dataclass(frozen=True)
class CameraConfig:
    """Configuração de uma câmera para o agent."""

    id: int
    name: str
    rtsp_url: str
    rtmp_push_url: str
    enabled: bool


@dataclass(frozen=True)
class AgentConfigResponse:
    """Resposta completa de configuração para o agent."""

    agent_id: int
    tenant_id: int
    poll_interval_seconds: int
    cameras: list[CameraConfig]


@dataclass(frozen=True)
class HeartbeatInput:
    """Dados do heartbeat enviado pelo agent."""

    version: str
    uptime_seconds: int
    cameras: dict  # camera_id -> status info


def create_agent(name: str, tenant_id: int) -> tuple[Agent, str]:
    """Cria um agent e gera sua API key.

    Args:
        name: Nome descritivo do agent.
        tenant_id: ID do tenant dono.

    Returns:
        Tupla (Agent, raw_api_key). A raw key só é retornada uma vez.
    """
    raw_key = secrets.token_urlsafe(48)
    agent = Agent.objects.create(
        name=name,
        api_key=raw_key,
        tenant_id=tenant_id,
    )

    publish_event("agent.created", {
        "agent_id": agent.id,
        "tenant_id": tenant_id,
        "name": name,
    })

    return agent, raw_key


def get_agent_config(agent: Agent) -> AgentConfigResponse:
    """Retorna configuração desejada para o agent.

    Lista câmeras do tenant associadas a este agent com suas
    push URLs RTMP.

    Args:
        agent: Instância do agent.

    Returns:
        Configuração completa incluindo lista de câmeras.
    """
    rtmp_base = getattr(settings, "MEDIAMTX_RTMP_URL", "rtmp://localhost:1935")

    cameras = agent.cameras.all()
    camera_configs = [
        CameraConfig(
            id=cam.id,
            name=cam.name,
            rtsp_url=cam.rtsp_url,
            rtmp_push_url=f"{rtmp_base}/tenant-{agent.tenant_id}/cam-{cam.id}",
            enabled=True,
        )
        for cam in cameras
    ]

    return AgentConfigResponse(
        agent_id=agent.id,
        tenant_id=agent.tenant_id,
        poll_interval_seconds=30,
        cameras=camera_configs,
    )


def process_heartbeat(agent: Agent, data: HeartbeatInput) -> None:
    """Processa heartbeat recebido de um agent.

    Atualiza timestamp, versão e status do agent.

    Args:
        agent: Instância do agent.
        data: Dados do heartbeat.
    """
    agent.last_heartbeat = timezone.now()
    agent.status = Agent.Status.ONLINE
    agent.version = data.version
    agent.save(update_fields=["last_heartbeat", "status", "version", "updated_at"])


def revoke_agent(agent_id: int, tenant_id: int) -> None:
    """Revoga (deleta) um agent.

    Args:
        agent_id: ID do agent.
        tenant_id: ID do tenant (para segurança multi-tenant).

    Raises:
        Agent.DoesNotExist: Agent não encontrado no tenant.
    """
    agent = Agent.objects.get(id=agent_id, tenant_id=tenant_id)
    agent.delete()

    publish_event("agent.revoked", {
        "agent_id": agent_id,
        "tenant_id": tenant_id,
    })
