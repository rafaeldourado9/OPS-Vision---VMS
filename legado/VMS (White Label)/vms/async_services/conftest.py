"""Fixtures para testes FastAPI."""
import pytest
from httpx import ASGITransport, AsyncClient

from main import app


import pytest_asyncio

@pytest_asyncio.fixture
async def async_client():
    """Client HTTP assíncrono para testes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
