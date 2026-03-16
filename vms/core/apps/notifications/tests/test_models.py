"""Testes para os modelos de notificações."""
import pytest
from apps.users.models import Tenant

from apps.notifications.models import NotificationLog, NotificationRule


@pytest.mark.django_db
class TestNotificationModels:

    @pytest.fixture
    def tenant(self):
        return Tenant.objects.create(name="Test Tenant")

    def test_create_notification_rule(self, tenant):
        """Pode criar uma NotificationRule."""
        rule = NotificationRule.objects.create(
            tenant=tenant,
            name="Alerta ALPR",
            event_type_pattern="detection.alpr",
            channel=NotificationRule.Channel.WEBHOOK,
            destination="https://example.com/webhook",
        )
        assert rule.id is not None
        assert str(rule) == "Alerta ALPR (detection.alpr -> webhook)"
        assert rule.is_active is True

    def test_create_notification_log(self, tenant):
        """Pode criar um NotificationLog atrelado a uma regra."""
        rule = NotificationRule.objects.create(
            tenant=tenant,
            name="Alerta",
            event_type_pattern="camera.*",
            destination="http://test",
        )
        log = NotificationLog.objects.create(
            rule=rule,
            event_id=42,
            event_type="camera.online",
            status="success",
            response_code=200,
            response_body="ok",
        )
        assert log.id is not None
        assert log.rule == rule
        assert "success" in str(log)
