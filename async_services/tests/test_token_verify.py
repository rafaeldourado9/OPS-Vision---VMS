"""Testes para o endpoint de verificação de token do MediaMTX."""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest

SECRET_KEY = "test-secret-key-for-tests"


def _make_token(camera_id: int, tenant_id: int, expired: bool = False) -> str:
    """Helper: cria token de stream para testes."""
    exp = datetime.now(tz=timezone.utc) + (
        timedelta(seconds=-1) if expired else timedelta(hours=1)
    )
    payload = {
        "camera_id": camera_id,
        "tenant_id": tenant_id,
        "type": "stream",
        "exp": exp,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


@pytest.mark.asyncio
class TestStreamTokenVerifyEndpoint:
    """Testes do endpoint POST /streaming/token/verify/."""

    async def test_valid_token_matching_path_returns_200(self, async_client):
        """Token válido com path correspondente retorna 200."""
        token = _make_token(camera_id=1, tenant_id=1)

        with patch.dict(os.environ, {"DJANGO_SECRET_KEY": SECRET_KEY}):
            response = await async_client.post(
                "/streaming/token/verify/",
                json={
                    "action": "read",
                    "path": "tenant-1/cam-1",
                    "query": f"token={token}",
                    "protocol": "hls",
                    "user": "",
                    "password": "",
                },
            )

        assert response.status_code == 200

    async def test_invalid_token_returns_403(self, async_client):
        """Token inválido retorna 403."""
        with patch.dict(os.environ, {"DJANGO_SECRET_KEY": SECRET_KEY}):
            response = await async_client.post(
                "/streaming/token/verify/",
                json={
                    "action": "read",
                    "path": "tenant-1/cam-1",
                    "query": "token=token.invalido.aqui",
                    "protocol": "hls",
                    "user": "",
                    "password": "",
                },
            )

        assert response.status_code == 403

    async def test_expired_token_returns_403(self, async_client):
        """Token expirado retorna 403."""
        token = _make_token(camera_id=1, tenant_id=1, expired=True)

        with patch.dict(os.environ, {"DJANGO_SECRET_KEY": SECRET_KEY}):
            response = await async_client.post(
                "/streaming/token/verify/",
                json={
                    "action": "read",
                    "path": "tenant-1/cam-1",
                    "query": f"token={token}",
                    "protocol": "hls",
                    "user": "",
                    "password": "",
                },
            )

        assert response.status_code == 403

    async def test_token_path_mismatch_returns_403(self, async_client):
        """Token válido mas path diferente do token retorna 403."""
        # Token para cam-1 mas path da requisição é cam-99
        token = _make_token(camera_id=1, tenant_id=1)

        with patch.dict(os.environ, {"DJANGO_SECRET_KEY": SECRET_KEY}):
            response = await async_client.post(
                "/streaming/token/verify/",
                json={
                    "action": "read",
                    "path": "tenant-1/cam-99",
                    "query": f"token={token}",
                    "protocol": "hls",
                    "user": "",
                    "password": "",
                },
            )

        assert response.status_code == 403

    async def test_tenant_mismatch_returns_403(self, async_client):
        """Token de tenant diferente do path retorna 403."""
        # Token para tenant-1 mas path pertence a tenant-2
        token = _make_token(camera_id=1, tenant_id=2)

        with patch.dict(os.environ, {"DJANGO_SECRET_KEY": SECRET_KEY}):
            response = await async_client.post(
                "/streaming/token/verify/",
                json={
                    "action": "read",
                    "path": "tenant-1/cam-1",
                    "query": f"token={token}",
                    "protocol": "hls",
                    "user": "",
                    "password": "",
                },
            )

        assert response.status_code == 403

    async def test_publish_action_allowed_without_token(self, async_client):
        """Ação de publish (câmera IP) é sempre permitida sem token."""
        with patch.dict(os.environ, {"DJANGO_SECRET_KEY": SECRET_KEY}):
            response = await async_client.post(
                "/streaming/token/verify/",
                json={
                    "action": "publish",
                    "path": "tenant-1/cam-1",
                    "query": "",
                    "protocol": "rtsp",
                    "user": "",
                    "password": "",
                },
            )

        assert response.status_code == 200

    async def test_missing_token_in_query_returns_403(self, async_client):
        """Ausência de token na query retorna 403 para read."""
        with patch.dict(os.environ, {"DJANGO_SECRET_KEY": SECRET_KEY}):
            response = await async_client.post(
                "/streaming/token/verify/",
                json={
                    "action": "read",
                    "path": "tenant-1/cam-1",
                    "query": "",
                    "protocol": "hls",
                    "user": "",
                    "password": "",
                },
            )

        assert response.status_code == 403

    async def test_webrtc_with_valid_token_returns_200(self, async_client):
        """WebRTC com token válido retorna 200."""
        token = _make_token(camera_id=5, tenant_id=3)

        with patch.dict(os.environ, {"DJANGO_SECRET_KEY": SECRET_KEY}):
            response = await async_client.post(
                "/streaming/token/verify/",
                json={
                    "action": "read",
                    "path": "tenant-3/cam-5",
                    "query": f"token={token}",
                    "protocol": "webrtc",
                    "user": "",
                    "password": "",
                },
            )

        assert response.status_code == 200
