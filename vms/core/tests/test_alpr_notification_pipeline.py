"""Teste de integração: Fluxo ALPR → Event → Notification.

Testa o pipeline completo: uma detecção ALPR é processada,
o evento é criado no banco, e as regras de notificação
correspondentes são avaliadas e despachadas.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.services import ALPRDetectionInput, process_alpr_detection
from apps.notifications.models import NotificationRule
from apps.notifications.services import evaluate_notification_rules
from tests.factories import CameraFactory, TenantFactory


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


class TestALPRToNotificationPipeline:
    """Teste E2E do fluxo ALPR → Event → Notification."""

    def setup_method(self):
        """Setup: tenant, câmera, regra de notificação."""
        self.tenant = TenantFactory()
        self.camera = CameraFactory(tenant=self.tenant, is_online=True)
        self.rule = NotificationRule.objects.create(
            tenant=self.tenant,
            name="Alerta ALPR",
            event_type_pattern="detection.alpr",
            channel="webhook",
            destination="https://hooks.example.com/alpr",
            is_active=True,
        )

    @patch("apps.events.services.publish_event")
    @patch("apps.notifications.services.current_app")
    def test_alpr_detection_triggers_notification(
        self, mock_celery, mock_publish
    ):
        """Detecção ALPR → Evento criado → Regra avaliada → Task despachada."""
        data = ALPRDetectionInput(
            plate="ABC1D23",
            camera_id=self.camera.id,
            confidence=0.95,
            timestamp=datetime(2026, 3, 13, 10, 30, tzinfo=timezone.utc),
            image_url="http://cam.local/snapshot.jpg",
        )

        # Step 1: Processa detecção ALPR
        event = process_alpr_detection(data)
        assert event is not None
        assert event.event_type == "alpr.detected"
        assert event.plate == "ABC1D23"
        assert event.tenant == self.tenant

        # Step 2: Verifica que publish_event foi chamado
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "detection.alpr"
        assert call_args[0][1]["event_id"] == event.id
        assert call_args[0][1]["plate"] == "ABC1D23"
        assert call_args[0][1]["camera_id"] == self.camera.id
        assert call_args[0][1]["tenant_id"] == self.tenant.id

        # Step 3: Simula o consumer avaliando as regras
        evaluate_notification_rules(
            event_type="detection.alpr",
            tenant_id=self.tenant.id,
            payload={"event_id": event.id, "plate": "ABC1D23"},
        )

        # Step 4: Verifica que Celery task de webhook foi despachada
        mock_celery.send_task.assert_called_once()
        send_args = mock_celery.send_task.call_args
        assert send_args[0][0] == "notifications.send_webhook"
        assert send_args[1]["kwargs"]["rule_id"] == self.rule.id
        assert send_args[1]["kwargs"]["event_id"] == event.id

    @patch("apps.events.services.publish_event")
    @patch("apps.notifications.services.current_app")
    def test_no_notification_when_rule_inactive(
        self, mock_celery, mock_publish
    ):
        """Regra inativa não gera notificação."""
        self.rule.is_active = False
        self.rule.save()

        data = ALPRDetectionInput(
            plate="XYZ9876",
            camera_id=self.camera.id,
            confidence=0.90,
            timestamp=datetime(2026, 3, 13, 10, 31, tzinfo=timezone.utc),
        )

        event = process_alpr_detection(data)
        assert event is not None

        evaluate_notification_rules(
            event_type="detection.alpr",
            tenant_id=self.tenant.id,
            payload={"event_id": event.id},
        )

        mock_celery.send_task.assert_not_called()

    @patch("apps.events.services.publish_event")
    @patch("apps.notifications.services.current_app")
    def test_no_notification_when_pattern_mismatch(
        self, mock_celery, mock_publish
    ):
        """Regra com padrão diferente não é acionada."""
        self.rule.event_type_pattern = "camera.offline"
        self.rule.save()

        data = ALPRDetectionInput(
            plate="DEF4567",
            camera_id=self.camera.id,
            confidence=0.88,
            timestamp=datetime(2026, 3, 13, 10, 32, tzinfo=timezone.utc),
        )

        event = process_alpr_detection(data)
        assert event is not None

        evaluate_notification_rules(
            event_type="detection.alpr",
            tenant_id=self.tenant.id,
            payload={"event_id": event.id},
        )

        mock_celery.send_task.assert_not_called()

    @patch("apps.events.services.publish_event")
    @patch("apps.notifications.services.current_app")
    def test_wildcard_pattern_matches(
        self, mock_celery, mock_publish
    ):
        """Regra com wildcard 'detection.*' captura ALPR."""
        self.rule.event_type_pattern = "detection.*"
        self.rule.save()

        data = ALPRDetectionInput(
            plate="GHI7890",
            camera_id=self.camera.id,
            confidence=0.92,
            timestamp=datetime(2026, 3, 13, 10, 33, tzinfo=timezone.utc),
        )

        event = process_alpr_detection(data)
        evaluate_notification_rules(
            event_type="detection.alpr",
            tenant_id=self.tenant.id,
            payload={"event_id": event.id},
        )

        mock_celery.send_task.assert_called_once()

    @patch("apps.events.services.publish_event")
    @patch("apps.notifications.services.current_app")
    def test_duplicate_alpr_no_event_no_notification(
        self, mock_celery, mock_publish
    ):
        """Detecção ALPR duplicada não gera evento nem notificação."""
        data = ALPRDetectionInput(
            plate="ABC1D23",
            camera_id=self.camera.id,
            confidence=0.95,
            timestamp=datetime(2026, 3, 13, 10, 30, tzinfo=timezone.utc),
        )

        # Primeira detecção: cria evento
        event1 = process_alpr_detection(data)
        assert event1 is not None

        # Segunda detecção idêntica dentro do TTL: duplicata
        event2 = process_alpr_detection(data)
        assert event2 is None

        # Apenas uma chamada a publish_event (primeira)
        assert mock_publish.call_count == 1

    @patch("apps.events.services.publish_event")
    @patch("apps.notifications.services.current_app")
    def test_cross_tenant_rule_not_triggered(
        self, mock_celery, mock_publish
    ):
        """Regra de outro tenant não é acionada pelo evento."""
        other_tenant = TenantFactory()
        NotificationRule.objects.create(
            tenant=other_tenant,
            name="Regra Outro Tenant",
            event_type_pattern="detection.alpr",
            channel="webhook",
            destination="https://other.example.com/hook",
            is_active=True,
        )

        data = ALPRDetectionInput(
            plate="JKL3456",
            camera_id=self.camera.id,
            confidence=0.91,
            timestamp=datetime(2026, 3, 13, 10, 34, tzinfo=timezone.utc),
        )

        event = process_alpr_detection(data)

        # Avalia com tenant correto: apenas a regra do self.tenant é acionada
        evaluate_notification_rules(
            event_type="detection.alpr",
            tenant_id=self.tenant.id,
            payload={"event_id": event.id},
        )

        # Apenas 1 chamada (regra do self.tenant)
        assert mock_celery.send_task.call_count == 1
