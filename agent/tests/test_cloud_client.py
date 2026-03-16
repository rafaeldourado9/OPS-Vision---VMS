"""Testes para agent/cloud_client.py."""
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from agent.cloud_client import AuthenticationError, CloudClient
from agent.config import AgentConfig


@pytest.fixture
def config():
    """Configuração de teste."""
    return AgentConfig(
        api_url="https://api.example.com/api/v1",
        api_key="test-key-123",
    )


@pytest.fixture
def client(config):
    """Cliente de teste."""
    return CloudClient(config)


def _mock_response(status_code: int = 200, json_data: dict | None = None):
    """Cria um httpx.Response mockado."""
    response = httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=httpx.Request("GET", "https://api.example.com"),
    )
    return response


class TestGetConfig:
    """Testes para CloudClient.get_config()."""

    @pytest.mark.asyncio
    async def test_returns_cameras(self, client):
        """Parseia resposta JSON em list[CameraConfig]."""
        response_data = {
            "agent_id": 1,
            "tenant_id": 1,
            "poll_interval_seconds": 30,
            "cameras": [
                {
                    "id": 5,
                    "name": "Entrada",
                    "rtsp_url": "rtsp://192.168.1.100:554/stream",
                    "rtmp_push_url": "rtmp://cloud:1935/tenant-1/cam-5",
                    "enabled": True,
                },
                {
                    "id": 8,
                    "name": "Estacionamento",
                    "rtsp_url": "rtsp://192.168.1.101:554/stream",
                    "rtmp_push_url": "rtmp://cloud:1935/tenant-1/cam-8",
                    "enabled": False,
                },
            ],
        }
        mock_resp = _mock_response(200, response_data)
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.cloud_client.httpx.AsyncClient", return_value=mock_client):
            cameras = await client.get_config()

        assert len(cameras) == 2
        assert cameras[0].id == 5
        assert cameras[0].name == "Entrada"
        assert cameras[0].rtsp_url == "rtsp://192.168.1.100:554/stream"
        assert cameras[0].rtmp_push_url == "rtmp://cloud:1935/tenant-1/cam-5"
        assert cameras[0].enabled is True
        assert cameras[1].enabled is False

    @pytest.mark.asyncio
    async def test_sends_auth_header(self, client):
        """Header Authorization: Agent <key> está presente."""
        mock_resp = _mock_response(200, {"cameras": []})
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.cloud_client.httpx.AsyncClient", return_value=mock_client):
            await client.get_config()

        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Authorization"] == "Agent test-key-123"

    @pytest.mark.asyncio
    async def test_handles_timeout(self, client):
        """Timeout retorna lista vazia sem crashar."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Connection timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.cloud_client.httpx.AsyncClient", return_value=mock_client):
            cameras = await client.get_config()

        assert cameras == []

    @pytest.mark.asyncio
    async def test_handles_401(self, client):
        """Erro HTTP 401 levanta AuthenticationError."""
        mock_resp = _mock_response(401, {"detail": "API key inválida."})
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.cloud_client.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AuthenticationError):
                await client.get_config()

    @pytest.mark.asyncio
    async def test_handles_server_error(self, client):
        """Erro HTTP 500 retorna lista vazia."""
        mock_resp = _mock_response(500, {"detail": "Internal Server Error"})
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.cloud_client.httpx.AsyncClient", return_value=mock_client):
            cameras = await client.get_config()

        assert cameras == []


class TestSendHeartbeat:
    """Testes para CloudClient.send_heartbeat()."""

    @pytest.mark.asyncio
    async def test_success(self, client):
        """POST com body correto retorna True."""
        mock_resp = _mock_response(200, {"status": "ok"})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.cloud_client.httpx.AsyncClient", return_value=mock_client):
            result = await client.send_heartbeat(
                uptime_seconds=120,
                cameras_status={"5": {"running": True}},
            )

        assert result is True

        call_kwargs = mock_client.post.call_args
        json_body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert json_body["uptime_seconds"] == 120
        assert json_body["version"] is not None
        assert "5" in json_body["cameras"]

    @pytest.mark.asyncio
    async def test_handles_error(self, client):
        """Erro HTTP retorna False sem crashar."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.cloud_client.httpx.AsyncClient", return_value=mock_client):
            result = await client.send_heartbeat(
                uptime_seconds=120,
                cameras_status={},
            )

        assert result is False
