"""Testes para o endpoint SSE."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
class TestSSEEndpoint:
    """Testes do endpoint GET /sse/."""

    async def test_missing_token_returns_401(self, async_client):
        """Requisição sem token retorna 401."""
        response = await async_client.get("/sse/")
        assert response.status_code == 401

    async def test_invalid_token_returns_401(self, async_client):
        """Token inválido retorna 401."""
        from fastapi import HTTPException

        with patch(
            "routers.sse.validate_token",
            side_effect=HTTPException(status_code=401, detail="Token inválido"),
        ):
            response = await async_client.get("/sse/?token=bad-token")
        assert response.status_code == 401

    async def test_valid_token_returns_event_stream(self, async_client):
        """Token válido retorna content-type text/event-stream."""
        mock_user = {"id": 1, "tenant_id": 42}

        async def mock_subscribe(channel, tenant_id):
            # Gerador que emite uma mensagem e encerra
            yield '{"type": "camera_status", "camera_id": 1, "is_online": true, "tenant_id": 42}'

        with patch("routers.sse.validate_token", return_value=mock_user), \
             patch("routers.sse.subscribe_to_channel", side_effect=mock_subscribe):
            response = await async_client.get(
                "/sse/?token=valid-token",
                headers={"Accept": "text/event-stream"},
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    async def test_sse_messages_filtered_by_tenant(self, async_client):
        """Mensagens de outro tenant não são enviadas."""
        mock_user = {"id": 1, "tenant_id": 42}

        # subscribe_to_channel recebe tenant_id — verifica o argumento
        captured_tenant = {}

        async def mock_subscribe(channel, tenant_id):
            captured_tenant["value"] = tenant_id
            return
            yield  # torna gerador assíncrono

        with patch("routers.sse.validate_token", return_value=mock_user), \
             patch("routers.sse.subscribe_to_channel", side_effect=mock_subscribe):
            await async_client.get("/sse/?token=valid-token")

        assert captured_tenant.get("value") == 42
