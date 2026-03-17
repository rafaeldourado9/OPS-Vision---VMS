"""Tests for authentication endpoint throttling.

Verifica que os endpoints de autenticação aplicam rate limits distintos:
- Usuários anônimos: 5 req/min por IP
- Usuários autenticados: 60 req/min por usuário
"""
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from config.urls import AuthAnonRateThrottle, AuthUserRateThrottle


@pytest.fixture()
def client():
    return APIClient()


@pytest.mark.django_db
class TestAuthThrottleClasses:
    """Testa as classes de throttle diretamente."""

    def test_anon_throttle_scope(self):
        assert AuthAnonRateThrottle.scope == "auth_anon"

    def test_user_throttle_scope(self):
        assert AuthUserRateThrottle.scope == "auth_user"

    def test_anon_throttle_inherits_anon_key(self, rf):
        """AuthAnonRateThrottle usa IP como chave de cache."""
        from rest_framework.throttling import AnonRateThrottle

        assert issubclass(AuthAnonRateThrottle, AnonRateThrottle)

    def test_user_throttle_inherits_user_key(self):
        """AuthUserRateThrottle usa user_id como chave de cache."""
        from rest_framework.throttling import UserRateThrottle

        assert issubclass(AuthUserRateThrottle, UserRateThrottle)


@pytest.mark.django_db
class TestTokenObtainThrottle:
    """Testa throttle nas views de token."""

    def test_obtain_view_uses_both_throttle_classes(self):
        from config.urls import ThrottledTokenObtainPairView

        throttle_classes = ThrottledTokenObtainPairView.throttle_classes
        assert AuthAnonRateThrottle in throttle_classes
        assert AuthUserRateThrottle in throttle_classes

    def test_refresh_view_uses_both_throttle_classes(self):
        from config.urls import ThrottledTokenRefreshView

        throttle_classes = ThrottledTokenRefreshView.throttle_classes
        assert AuthAnonRateThrottle in throttle_classes
        assert AuthUserRateThrottle in throttle_classes

    @pytest.mark.django_db
    def test_anon_rate_limit_exceeded_returns_429(self, client):
        """Após 5 requisições anônimas, retorna 429."""
        url = reverse("token_obtain")
        payload = {"username": "noexist", "password": "wrongpass"}
        call_count = {"n": 0}

        def mock_allow(self, request, view):
            call_count["n"] += 1
            return call_count["n"] <= 5

        with patch.object(AuthAnonRateThrottle, "allow_request", mock_allow), \
             patch.object(AuthAnonRateThrottle, "wait", return_value=60.0):
            for _ in range(5):
                client.post(url, payload, format="json")
            response = client.post(url, payload, format="json")
            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
