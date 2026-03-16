"""Testes para os services de notificações."""
from unittest.mock import patch

import pytest
from apps.users.models import Tenant

from apps.notifications.models import NotificationRule
from apps.notifications.services import evaluate_notification_rules


@pytest.mark.django_db
class TestEvaluateNotificationRules:

    @pytest.fixture
    def tenant(self):
        return Tenant.objects.create(name="Test Tenant")

    @pytest.fixture
    def rules(self, tenant):
        NotificationRule.objects.create(
            tenant=tenant,
            name="Rule ALPR",
            event_type_pattern="detection.alpr",
            destination="http://1",
        )
        NotificationRule.objects.create(
            tenant=tenant,
            name="Rule All Cameras",
            event_type_pattern="camera.*",
            destination="http://2",
        )
        NotificationRule.objects.create(
            tenant=tenant,
            name="Rule Faces (Inactive)",
            event_type_pattern="detection.facial",
            destination="http://3",
            is_active=False,
        )

    @patch("apps.notifications.services.current_app.send_task")
    def test_exact_match(self, mock_send_task, tenant, rules):
        """Evento detection.alpr deve invocar a regra correspondente."""
        payload = {"id": 10, "data": "test"}
        evaluate_notification_rules("detection.alpr", tenant.id, payload)

        mock_send_task.assert_called_once()
        kwargs = mock_send_task.call_args.kwargs.get("kwargs", {})
        assert kwargs["event_type"] == "detection.alpr"
        assert kwargs["event_id"] == 10
        assert kwargs["payload"] == payload

    @patch("apps.notifications.services.current_app.send_task")
    def test_wildcard_match(self, mock_send_task, tenant, rules):
        """Evento camera.online deve bater no pattern camera.*."""
        evaluate_notification_rules("camera.online", tenant.id, {"event_id": 99})

        mock_send_task.assert_called_once()
        kwargs = mock_send_task.call_args.kwargs.get("kwargs", {})
        assert kwargs["event_type"] == "camera.online"
        assert kwargs["event_id"] == 99

    @patch("apps.notifications.services.current_app.send_task")
    def test_inactive_rule_ignored(self, mock_send_task, tenant, rules):
        """Regra inativa não deve ser processada."""
        evaluate_notification_rules("detection.facial", tenant.id, {})
        mock_send_task.assert_not_called()

    @patch("apps.notifications.services.current_app.send_task")
    def test_no_match(self, mock_send_task, tenant, rules):
        """Evento desconhecido não dispara nada."""
        evaluate_notification_rules("system.reboot", tenant.id, {})
        mock_send_task.assert_not_called()
