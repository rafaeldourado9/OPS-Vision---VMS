"""Testes para stream tokens e endpoint /live/."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cameras.services import (
    StreamTokenExpiredError,
    StreamTokenInvalidError,
    generate_stream_token,
    verify_stream_token,
)
from tests.factories import CameraFactory, TenantFactory, UserFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestGenerateStreamToken:
    """Testes de geração de stream token."""

    def setup_method(self):
        self.tenant = TenantFactory()
        self.camera = CameraFactory(tenant=self.tenant, is_online=True)

    def test_returns_string(self):
        """Token gerado é uma string."""
        token = generate_stream_token(self.camera.id, self.tenant.id)
        assert isinstance(token, str)
        assert len(token) > 10

    def test_different_cameras_produce_different_tokens(self):
        """Câmeras diferentes geram tokens diferentes."""
        cam2 = CameraFactory(tenant=self.tenant)
        t1 = generate_stream_token(self.camera.id, self.tenant.id)
        t2 = generate_stream_token(cam2.id, self.tenant.id)
        assert t1 != t2

    def test_token_is_verifiable(self):
        """Token gerado pode ser verificado."""
        token = generate_stream_token(self.camera.id, self.tenant.id)
        payload = verify_stream_token(token)
        assert payload["camera_id"] == self.camera.id
        assert payload["tenant_id"] == self.tenant.id

    def test_token_contains_expiry(self):
        """Token decodificado contém campo de expiração."""
        import jwt
        from django.conf import settings

        token = generate_stream_token(self.camera.id, self.tenant.id)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        assert "exp" in payload


@pytest.mark.unit
@pytest.mark.django_db
class TestVerifyStreamToken:
    """Testes de verificação de stream token."""

    def setup_method(self):
        self.tenant = TenantFactory()
        self.camera = CameraFactory(tenant=self.tenant)

    def test_valid_token_returns_payload(self):
        """Token válido retorna camera_id e tenant_id."""
        token = generate_stream_token(self.camera.id, self.tenant.id)
        payload = verify_stream_token(token)

        assert payload["camera_id"] == self.camera.id
        assert payload["tenant_id"] == self.tenant.id

    def test_invalid_token_raises_error(self):
        """Token inválido lança StreamTokenInvalidError."""
        with pytest.raises(StreamTokenInvalidError):
            verify_stream_token("token.invalido.aqui")

    def test_tampered_token_raises_error(self):
        """Token adulterado lança StreamTokenInvalidError."""
        import base64, json

        token = generate_stream_token(self.camera.id, self.tenant.id)
        parts = token.split(".")
        # Altera o payload (parte do meio) para câmera 99999
        bad_payload = base64.urlsafe_b64encode(
            json.dumps({"camera_id": 99999, "tenant_id": self.tenant.id}).encode()
        ).decode().rstrip("=")
        bad_token = f"{parts[0]}.{bad_payload}.{parts[2]}"

        with pytest.raises(StreamTokenInvalidError):
            verify_stream_token(bad_token)

    def test_expired_token_raises_error(self):
        """Token expirado lança StreamTokenExpiredError."""
        import jwt
        from datetime import datetime, timezone as dt_timezone
        from django.conf import settings

        payload = {
            "camera_id": self.camera.id,
            "tenant_id": self.tenant.id,
            "type": "stream",
            "exp": datetime.now(tz=dt_timezone.utc) - timedelta(seconds=1),
        }
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        with pytest.raises(StreamTokenExpiredError):
            verify_stream_token(expired_token)

    def test_wrong_type_raises_error(self):
        """Token de outro tipo (ex: user JWT) lança StreamTokenInvalidError."""
        import jwt
        from datetime import datetime, timezone as dt_timezone
        from django.conf import settings

        payload = {
            "camera_id": self.camera.id,
            "tenant_id": self.tenant.id,
            "type": "user_auth",  # tipo errado
            "exp": datetime.now(tz=dt_timezone.utc) + timedelta(hours=1),
        }
        wrong_token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        with pytest.raises(StreamTokenInvalidError):
            verify_stream_token(wrong_token)


@pytest.mark.unit
@pytest.mark.django_db
class TestLiveStreamEndpoint:
    """Testes do endpoint GET /api/v1/cameras/{id}/live/."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.camera = CameraFactory(tenant=self.user.tenant, is_online=True)

    def test_returns_200_for_online_camera(self):
        """Câmera online retorna 200."""
        response = self.client.get(f"/api/v1/cameras/{self.camera.id}/live/")
        assert response.status_code == status.HTTP_200_OK

    def test_response_contains_hls_url(self):
        """Resposta contém hls_url."""
        response = self.client.get(f"/api/v1/cameras/{self.camera.id}/live/")
        assert "hls_url" in response.data
        assert response.data["hls_url"].startswith("http")
        assert "index.m3u8" in response.data["hls_url"]

    def test_response_contains_webrtc_url(self):
        """Resposta contém webrtc_url."""
        response = self.client.get(f"/api/v1/cameras/{self.camera.id}/live/")
        assert "webrtc_url" in response.data
        assert response.data["webrtc_url"].startswith("http")
        assert "whep" in response.data["webrtc_url"]

    def test_response_contains_token_field(self):
        """Resposta contém campo token (stub — vazio até implementação)."""
        response = self.client.get(f"/api/v1/cameras/{self.camera.id}/live/")
        assert "token" in response.data

    def test_response_contains_expires_at(self):
        """Resposta contém expires_at em ISO 8601."""
        response = self.client.get(f"/api/v1/cameras/{self.camera.id}/live/")
        assert "expires_at" in response.data

    def test_response_contains_is_online(self):
        """Resposta inclui status is_online da câmera."""
        response = self.client.get(f"/api/v1/cameras/{self.camera.id}/live/")
        assert "is_online" in response.data
        assert response.data["is_online"] is True

    def test_urls_do_not_contain_token_yet(self):
        """URLs ainda não contêm token (stub — aguardando implementação)."""
        response = self.client.get(f"/api/v1/cameras/{self.camera.id}/live/")
        assert "token=" not in response.data["hls_url"]
        assert "token=" not in response.data["webrtc_url"]

    def test_urls_contain_camera_path(self):
        """URLs contêm o path correto da câmera no MediaMTX."""
        response = self.client.get(f"/api/v1/cameras/{self.camera.id}/live/")
        expected_path = f"tenant-{self.user.tenant.id}/cam-{self.camera.id}"
        assert expected_path in response.data["hls_url"]
        assert expected_path in response.data["webrtc_url"]

    def test_wrong_tenant_returns_404(self):
        """Câmera de outro tenant retorna 404."""
        other_camera = CameraFactory(is_online=True)
        response = self.client.get(f"/api/v1/cameras/{other_camera.id}/live/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_returns_401(self):
        """Sem autenticação retorna 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get(f"/api/v1/cameras/{self.camera.id}/live/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_offline_camera_still_returns_urls(self):
        """Câmera offline ainda retorna URLs (stream pode estar temporariamente down)."""
        offline_camera = CameraFactory(tenant=self.user.tenant, is_online=False)
        response = self.client.get(f"/api/v1/cameras/{offline_camera.id}/live/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_online"] is False
        assert "hls_url" in response.data
