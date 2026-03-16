"""Testes para o webservice/views das notificações."""
import pytest
from apps.users.models import Tenant
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.notifications.models import NotificationLog, NotificationRule

User = get_user_model()


@pytest.fixture
def auth_client():
    tenant = Tenant.objects.create(name="T1", slug="t1-notif")
    user = User.objects.create(email="user@t1.com", tenant=tenant)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, tenant, user


@pytest.fixture
def other_tenant_rule():
    t2 = Tenant.objects.create(name="T2", slug="t2-notif")
    return NotificationRule.objects.create(
        tenant=t2, name="Other", destination="http://other"
    )


@pytest.mark.django_db
class TestNotificationRuleAPI:
    def test_create_rule(self, auth_client):
        """Verifica se a regra é criada e amarrada ao tenant do request."""
        client, tenant, _ = auth_client
        data = {
            "name": "Integration Rule",
            "event_type_pattern": "camera.offline",
            "destination": "https://webhook.site/xxx",
        }
        res = client.post("/api/v1/notifications/rules/", data, format="json")

        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["name"] == "Integration Rule"

        rule = NotificationRule.objects.get(id=res.data["id"])
        # O tenant é atrelado mesmo sem estar no payload de request
        assert rule.tenant == tenant

    def test_list_rules_tenant_isolation(self, auth_client, other_tenant_rule):
        """Garante que só vemos as regras do nosso próprio tenant."""
        client, tenant, _ = auth_client

        NotificationRule.objects.create(
            tenant=tenant, name="My rule 1", destination="http://foo"
        )
        NotificationRule.objects.create(
            tenant=tenant, name="My rule 2", destination="http://bar"
        )

        res = client.get("/api/v1/notifications/rules/")
        assert res.status_code == status.HTTP_200_OK

        # As DUAS regras locais tem que estar; a "Other" não
        results = res.data if isinstance(res.data, list) else res.data.get("results", [])
        assert len(results) == 2


@pytest.mark.django_db
class TestNotificationLogAPI:
    def test_list_logs_tenant_isolation(self, auth_client, other_tenant_rule):
        """Pode listar os logs das SUAS regras de notificação."""
        client, tenant, _ = auth_client

        my_rule = NotificationRule.objects.create(
            tenant=tenant, name="Mine", destination="http://mine"
        )
        NotificationLog.objects.create(rule=my_rule, status="success")
        NotificationLog.objects.create(rule=my_rule, status="failed")

        # Log pro outro tenant
        NotificationLog.objects.create(rule=other_tenant_rule, status="success")

        res = client.get("/api/v1/notifications/logs/")
        assert res.status_code == status.HTTP_200_OK

        results = res.data if isinstance(res.data, list) else res.data.get("results", [])
        assert len(results) == 2
