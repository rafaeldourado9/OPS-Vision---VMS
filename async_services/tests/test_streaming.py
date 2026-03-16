"""Testes para rotas de streaming."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
class TestStreamingRoutes:
    """Testes do endpoint de streams."""

    async def test_list_streams_returns_empty(self, async_client):
        """Lista de streams retorna lista vazia."""
        with patch(
            "routers.streaming.list_active_streams",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await async_client.get("/streams/")

        assert response.status_code == 200
        assert response.json() == {"streams": []}

    async def test_list_streams_returns_active(self, async_client):
        """Lista de streams retorna streams ativos."""
        mock_streams = [
            {
                "path": "tenant-1/cam-1",
                "source": "rtspSource",
                "ready": True,
                "readers": 2,
            }
        ]
        with patch(
            "routers.streaming.list_active_streams",
            new_callable=AsyncMock,
            return_value=mock_streams,
        ):
            response = await async_client.get("/streams/")

        assert response.status_code == 200
        assert len(response.json()["streams"]) == 1
