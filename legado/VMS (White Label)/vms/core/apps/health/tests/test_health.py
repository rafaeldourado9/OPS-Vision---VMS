"""Testes para o health check endpoint."""
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


class TestHealthCheckEndpoint:
    """Testa GET /api/v1/health/."""

    def setup_method(self):
        self.client = APIClient()
        self.url = "/api/v1/health/"

    @patch("apps.health.views._check_rabbitmq", return_value="ok")
    @patch("apps.health.views._check_redis", return_value="ok")
    @patch("apps.health.views._check_db", return_value="ok")
    def test_returns_200_when_all_healthy(self, mock_db, mock_redis, mock_rmq):
        """Retorna 200 quando todos os serviços estão ok."""
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "healthy"
        assert response.data["services"]["db"] == "ok"
        assert response.data["services"]["redis"] == "ok"
        assert response.data["services"]["rabbitmq"] == "ok"

    @patch("apps.health.views._check_rabbitmq", return_value="ok")
    @patch("apps.health.views._check_redis", return_value="ok")
    @patch("apps.health.views._check_db", return_value="error")
    def test_returns_503_when_db_down(self, mock_db, mock_redis, mock_rmq):
        """Retorna 503 quando DB está fora."""
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "degraded"
        assert response.data["services"]["db"] == "error"

    @patch("apps.health.views._check_rabbitmq", return_value="ok")
    @patch("apps.health.views._check_redis", return_value="error")
    @patch("apps.health.views._check_db", return_value="ok")
    def test_returns_503_when_redis_down(self, mock_db, mock_redis, mock_rmq):
        """Retorna 503 quando Redis está fora."""
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["services"]["redis"] == "error"

    @patch("apps.health.views._check_rabbitmq", return_value="error")
    @patch("apps.health.views._check_redis", return_value="ok")
    @patch("apps.health.views._check_db", return_value="ok")
    def test_returns_503_when_rabbitmq_down(self, mock_db, mock_redis, mock_rmq):
        """Retorna 503 quando RabbitMQ está fora."""
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["services"]["rabbitmq"] == "error"

    @patch("apps.health.views._check_rabbitmq", return_value="ok")
    @patch("apps.health.views._check_redis", return_value="ok")
    @patch("apps.health.views._check_db", return_value="ok")
    def test_does_not_require_authentication(self, mock_db, mock_redis, mock_rmq):
        """Endpoint não requer autenticação."""
        # Client sem credentials
        response = APIClient().get(self.url)
        assert response.status_code == status.HTTP_200_OK

    @patch("apps.health.views._check_rabbitmq", return_value="ok")
    @patch("apps.health.views._check_redis", return_value="ok")
    @patch("apps.health.views._check_db", return_value="ok")
    def test_response_structure(self, mock_db, mock_redis, mock_rmq):
        """Resposta tem estrutura correta."""
        response = self.client.get(self.url)
        assert "status" in response.data
        assert "services" in response.data
        assert set(response.data["services"].keys()) == {"db", "redis", "rabbitmq"}
