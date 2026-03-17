"""Testes para as tarefas Celery de notificações."""
import hashlib
import hmac
import json
from unittest.mock import patch

import httpx
import pytest
from apps.users.models import Tenant

from apps.notifications.models import NotificationLog, NotificationRule
from apps.notifications.tasks import _compute_hmac_signature, send_webhook_notification


@pytest.mark.django_db
class TestSendWebhookNotification:

    @pytest.fixture
    def tenant(self):
        return Tenant.objects.create(name="Test Tenant")

    @pytest.fixture
    def rule(self, tenant):
        return NotificationRule.objects.create(
            tenant=tenant,
            name="Test Webhook",
            event_type_pattern="camera.online",
            channel=NotificationRule.Channel.WEBHOOK,
            destination="http://example.com/webhook",
        )

    @patch("apps.notifications.tasks.httpx.Client")
    def test_success_webhook(self, mock_client_cls, rule):
        """Webhook respondendo 200 gera log de sucesso."""
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = patch("httpx.Response").start()
        mock_response.status_code = 200
        mock_response.text = '{"success": true}'
        mock_response.is_success = True
        mock_client.post.return_value = mock_response

        payload = {"camera_id": 42}
        result = send_webhook_notification(
            rule_id=rule.id,
            event_type="camera.online",
            event_id=99,
            payload=payload,
        )

        assert result is True
        mock_client.post.assert_called_once_with(
            "http://example.com/webhook",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        log = NotificationLog.objects.first()
        assert log is not None
        assert log.rule == rule
        assert log.event_type == "camera.online"
        assert log.event_id == 99
        assert log.status == "success"
        assert log.response_code == 200
        assert log.response_body == '{"success": true}'

    @patch("apps.notifications.tasks.httpx.Client")
    def test_failed_webhook(self, mock_client_cls, rule):
        """Webhook com HTTP error status."""
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = patch("httpx.Response").start()
        mock_response.status_code = 500
        mock_response.text = '{"error": "Internal Server Error"}'
        mock_response.is_success = False
        mock_client.post.return_value = mock_response

        result = send_webhook_notification(
            rule_id=rule.id,
            event_type="camera.online",
            event_id=None,
            payload={},
        )

        assert result is False
        log = NotificationLog.objects.first()
        assert log.status == "failed"
        assert log.response_code == 500
        assert "Internal Server" in log.response_body

    @patch("apps.notifications.tasks.httpx.Client")
    def test_webhook_timeout(self, mock_client_cls, rule):
        """Timeout no webhook (ReadTimeout, etc)."""
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.side_effect = httpx.TimeoutException("Read timeout")

        result = send_webhook_notification(
            rule_id=rule.id,
            event_type="camera.online",
            event_id=None,
            payload={},
        )

        assert result is False
        log = NotificationLog.objects.first()
        assert log.status == "failed"
        assert log.response_code is None
        assert "Timeout" in log.response_body

    def test_rule_not_found(self):
        """Regra não existe -> não quebra, retorna False silencioso."""
        result = send_webhook_notification(
            rule_id=9999,
            event_type="camera.online",
            event_id=None,
            payload={},
        )

        assert result is False
        assert NotificationLog.objects.count() == 0


@pytest.mark.django_db
class TestWebhookHMAC:
    """Testes de assinatura HMAC-SHA256 nos webhooks."""

    @pytest.fixture
    def tenant(self):
        return Tenant.objects.create(name="HMAC Tenant")

    @pytest.fixture
    def rule_with_secret(self, tenant):
        return NotificationRule.objects.create(
            tenant=tenant,
            name="Signed Webhook",
            event_type_pattern="camera.online",
            channel=NotificationRule.Channel.WEBHOOK,
            destination="http://example.com/webhook",
            webhook_secret="my-secret-key-123",
        )

    @pytest.fixture
    def rule_without_secret(self, tenant):
        return NotificationRule.objects.create(
            tenant=tenant,
            name="Unsigned Webhook",
            event_type_pattern="camera.online",
            channel=NotificationRule.Channel.WEBHOOK,
            destination="http://example.com/webhook",
        )

    def test_compute_hmac_signature(self):
        """Verifica que _compute_hmac_signature gera assinatura correta."""
        payload = {"camera_id": 42, "status": "online"}
        secret = "test-secret"
        result = _compute_hmac_signature(secret, payload)

        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        expected = "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
        assert result == expected
        assert result.startswith("sha256=")

    @patch("apps.notifications.tasks.httpx.Client")
    def test_webhook_with_secret_includes_signature(
        self, mock_client_cls, rule_with_secret
    ):
        """Webhook com secret deve incluir header X-VMS-Signature."""
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = patch("httpx.Response").start()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_response.is_success = True
        mock_client.post.return_value = mock_response

        payload = {"camera_id": 42}
        send_webhook_notification(
            rule_id=rule_with_secret.id,
            event_type="camera.online",
            event_id=1,
            payload=payload,
        )

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert "X-VMS-Signature" in headers
        expected_sig = _compute_hmac_signature("my-secret-key-123", payload)
        assert headers["X-VMS-Signature"] == expected_sig

    @patch("apps.notifications.tasks.httpx.Client")
    def test_webhook_without_secret_no_signature(
        self, mock_client_cls, rule_without_secret
    ):
        """Webhook sem secret NÃO deve incluir header X-VMS-Signature."""
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = patch("httpx.Response").start()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_response.is_success = True
        mock_client.post.return_value = mock_response

        payload = {"camera_id": 42}
        send_webhook_notification(
            rule_id=rule_without_secret.id,
            event_type="camera.online",
            event_id=1,
            payload=payload,
        )

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert "X-VMS-Signature" not in headers
        assert headers == {"Content-Type": "application/json"}

    def test_hmac_deterministic(self):
        """Mesma payload + secret gera mesma assinatura."""
        payload = {"key": "value", "num": 123}
        sig1 = _compute_hmac_signature("secret", payload)
        sig2 = _compute_hmac_signature("secret", payload)
        assert sig1 == sig2

    def test_hmac_different_secrets_different_signatures(self):
        """Secrets diferentes geram assinaturas diferentes."""
        payload = {"key": "value"}
        sig1 = _compute_hmac_signature("secret-a", payload)
        sig2 = _compute_hmac_signature("secret-b", payload)
        assert sig1 != sig2
