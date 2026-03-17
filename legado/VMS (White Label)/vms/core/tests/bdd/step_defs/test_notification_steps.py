"""Step definitions para gerenciamento de notificações."""
import pytest
from pytest_bdd import given, parsers, scenario, then, when
from rest_framework import status
from rest_framework.test import APIClient

from apps.notifications.models import NotificationLog, NotificationRule
from tests.factories import TenantFactory, UserFactory

pytestmark = [pytest.mark.bdd, pytest.mark.django_db]


# Scenarios
@scenario(
    "../features/notification_management.feature",
    "Criar regra de notificação webhook",
)
def test_create_notification_rule():
    pass


@scenario(
    "../features/notification_management.feature",
    "Criar regra com webhook_secret",
)
def test_create_rule_with_secret():
    pass


@scenario(
    "../features/notification_management.feature",
    "Listar regras com isolamento de tenant",
)
def test_list_rules_tenant_isolation():
    pass


@scenario(
    "../features/notification_management.feature",
    "Desativar regra de notificação",
)
def test_deactivate_rule():
    pass


@scenario(
    "../features/notification_management.feature",
    "Deletar regra de notificação",
)
def test_delete_rule():
    pass


@scenario(
    "../features/notification_management.feature",
    "Listar logs de notificação",
)
def test_list_logs():
    pass


@scenario(
    "../features/notification_management.feature",
    "Isolamento de logs entre tenants",
)
def test_log_tenant_isolation():
    pass


# Given steps
@given(
    "que estou autenticado como operador de notificações",
    target_fixture="ctx",
)
def authenticated_user():
    """Cria usuário autenticado."""
    client = APIClient()
    user = UserFactory()
    client.force_authenticate(user=user)
    return {
        "client": client,
        "user": user,
        "tenant": user.tenant,
        "response": None,
        "rule": None,
    }


@given(parsers.parse("que existem {count:d} regras no meu tenant"))
def rules_in_my_tenant(ctx, count):
    """Cria regras no tenant do usuário."""
    for i in range(count):
        NotificationRule.objects.create(
            tenant=ctx["tenant"],
            name=f"Regra {i+1}",
            destination=f"https://hooks.example.com/{i}",
        )


@given(parsers.parse("existem {count:d} regras em outro tenant"))
def rules_in_other_tenant(ctx, count):
    """Cria regras em outro tenant."""
    other = TenantFactory()
    for i in range(count):
        NotificationRule.objects.create(
            tenant=other,
            name=f"Regra Outro {i+1}",
            destination=f"https://other.example.com/{i}",
        )


@given(parsers.parse('que existe uma regra ativa "{name}"'))
def active_rule_exists(ctx, name):
    """Cria regra ativa."""
    ctx["rule"] = NotificationRule.objects.create(
        tenant=ctx["tenant"],
        name=name,
        destination="https://hooks.example.com/alert",
        is_active=True,
    )


@given("que existe uma regra com logs de envio")
def rule_with_logs(ctx):
    """Cria regra com logs."""
    rule = NotificationRule.objects.create(
        tenant=ctx["tenant"],
        name="Regra com Logs",
        destination="https://hooks.example.com/logs",
    )
    ctx["rule"] = rule
    NotificationLog.objects.create(
        rule=rule,
        event_type="detection.alpr",
        status="success",
        response_code=200,
    )
    NotificationLog.objects.create(
        rule=rule,
        event_type="camera.offline",
        status="failed",
        response_code=500,
    )


@given("existem logs em outro tenant")
def logs_in_other_tenant(ctx):
    """Cria logs em outro tenant."""
    other = TenantFactory()
    other_rule = NotificationRule.objects.create(
        tenant=other,
        name="Regra Outro Tenant",
        destination="https://other.example.com/logs",
    )
    NotificationLog.objects.create(
        rule=other_rule,
        event_type="camera.online",
        status="success",
        response_code=200,
    )


# When steps
@when(
    parsers.parse(
        'eu crio uma regra "{name}" para o evento "{event_pattern}"'
        ' com destino "{destination}"'
    )
)
def create_rule(ctx, name, event_pattern, destination):
    """Cria regra de notificação."""
    data = {
        "name": name,
        "event_type_pattern": event_pattern,
        "destination": destination,
    }
    ctx["response"] = ctx["client"].post(
        "/api/v1/notifications/rules/",
        data,
        format="json",
    )


@when(
    parsers.parse(
        'eu crio uma regra "{name}" para o evento "{event_pattern}"'
        ' com destino "{destination}" e secret "{secret}"'
    )
)
def create_rule_with_secret(ctx, name, event_pattern, destination, secret):
    """Cria regra com webhook_secret."""
    data = {
        "name": name,
        "event_type_pattern": event_pattern,
        "destination": destination,
        "webhook_secret": secret,
    }
    ctx["response"] = ctx["client"].post(
        "/api/v1/notifications/rules/",
        data,
        format="json",
    )


@when("eu listo as regras de notificação")
def list_rules(ctx):
    """Lista regras."""
    ctx["response"] = ctx["client"].get("/api/v1/notifications/rules/")


@when("eu desativo a regra")
def deactivate_rule(ctx):
    """Desativa regra."""
    ctx["response"] = ctx["client"].patch(
        f"/api/v1/notifications/rules/{ctx['rule'].id}/",
        {"is_active": False},
        format="json",
    )


@when("eu deleto a regra de notificação")
def delete_rule(ctx):
    """Deleta regra."""
    ctx["rule_id"] = ctx["rule"].id
    ctx["response"] = ctx["client"].delete(
        f"/api/v1/notifications/rules/{ctx['rule'].id}/"
    )


@when("eu listo os logs de notificação")
def list_logs(ctx):
    """Lista logs."""
    ctx["response"] = ctx["client"].get("/api/v1/notifications/logs/")


# Then steps
@then("a regra é criada com sucesso")
def rule_created(ctx):
    """Verifica criação."""
    assert ctx["response"].status_code == status.HTTP_201_CREATED
    assert "id" in ctx["response"].data


@then("a regra pertence ao meu tenant")
def rule_belongs_to_tenant(ctx):
    """Verifica tenant da regra."""
    rule = NotificationRule.objects.get(id=ctx["response"].data["id"])
    assert rule.tenant == ctx["tenant"]


@then(parsers.parse('o canal padrão é "{channel}"'))
def default_channel(ctx, channel):
    """Verifica canal padrão."""
    rule = NotificationRule.objects.get(id=ctx["response"].data["id"])
    assert rule.channel == channel


@then("o webhook_secret não é exposto na resposta")
def secret_not_exposed(ctx):
    """Verifica que webhook_secret não está nos dados da resposta."""
    assert "webhook_secret" not in ctx["response"].data


@then(parsers.parse("vejo {count:d} regras"))
def see_rule_count(ctx, count):
    """Verifica quantidade de regras."""
    results = ctx["response"].data.get("results", ctx["response"].data)
    assert len(results) == count


@then("não vejo regras de outros tenants")
def no_other_tenant_rules(ctx):
    """Verifica isolamento."""
    results = ctx["response"].data.get("results", ctx["response"].data)
    tenant_id = ctx["tenant"].id
    for rule_data in results:
        rule = NotificationRule.objects.get(id=rule_data["id"])
        assert rule.tenant_id == tenant_id


@then("a regra está inativa")
def rule_is_inactive(ctx):
    """Verifica que a regra está inativa."""
    assert ctx["response"].status_code == status.HTTP_200_OK
    ctx["rule"].refresh_from_db()
    assert ctx["rule"].is_active is False


@then("a regra ainda existe no sistema")
def rule_still_exists(ctx):
    """Verifica que a regra ainda existe."""
    assert NotificationRule.objects.filter(id=ctx["rule"].id).exists()


@then("a regra é removida com sucesso")
def rule_deleted(ctx):
    """Verifica deleção."""
    assert ctx["response"].status_code == status.HTTP_204_NO_CONTENT
    assert not NotificationRule.objects.filter(id=ctx["rule_id"]).exists()


@then("vejo os logs da minha regra")
def see_my_logs(ctx):
    """Verifica que os logs são da minha regra."""
    results = ctx["response"].data.get("results", ctx["response"].data)
    assert len(results) >= 1
    for log_data in results:
        log = NotificationLog.objects.get(id=log_data["id"])
        assert log.rule.tenant == ctx["tenant"]


@then("os logs contêm status de envio")
def logs_have_status(ctx):
    """Verifica que logs contêm status."""
    results = ctx["response"].data.get("results", ctx["response"].data)
    for log_data in results:
        assert "status" in log_data
        assert log_data["status"] in ("success", "failed", "pending")


@then("não vejo logs de outros tenants")
def no_other_tenant_logs(ctx):
    """Verifica isolamento de logs."""
    results = ctx["response"].data.get("results", ctx["response"].data)
    for log_data in results:
        log = NotificationLog.objects.get(id=log_data["id"])
        assert log.rule.tenant == ctx["tenant"]
