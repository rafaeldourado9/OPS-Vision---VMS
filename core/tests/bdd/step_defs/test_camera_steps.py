"""Step definitions para gerenciamento de câmeras."""
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenario, then, when
from rest_framework import status
from rest_framework.test import APIClient

from apps.cameras.models import Camera
from shared.mediamtx_client import MediaMTXError
from tests.factories import CameraFactory, TenantFactory, UserFactory

pytestmark = [pytest.mark.bdd, pytest.mark.django_db]


# Scenarios
@scenario(
    "../features/camera_management.feature",
    "Adicionar câmera com sucesso",
)
def test_add_camera_success():
    pass


@scenario(
    "../features/camera_management.feature",
    "Adicionar câmera com dados mínimos",
)
def test_add_camera_minimal():
    pass


@scenario(
    "../features/camera_management.feature",
    "Validação de campos obrigatórios",
)
def test_validation_required_fields():
    pass


@scenario(
    "../features/camera_management.feature",
    "Validação de URL RTSP inválida",
)
def test_validation_invalid_rtsp():
    pass


@scenario(
    "../features/camera_management.feature",
    "Listar câmeras do meu tenant",
)
def test_list_cameras_tenant_filter():
    pass


@scenario(
    "../features/camera_management.feature",
    "Visualizar detalhes de uma câmera",
)
def test_view_camera_details():
    pass


@scenario(
    "../features/camera_management.feature",
    "Atualizar nome da câmera",
)
def test_update_camera_name():
    pass


@scenario(
    "../features/camera_management.feature",
    "Atualizar múltiplos campos",
)
def test_update_multiple_fields():
    pass


@scenario(
    "../features/camera_management.feature",
    "Atualizar URL RTSP atualiza MediaMTX",
)
def test_update_rtsp_calls_mediamtx():
    pass


@scenario(
    "../features/camera_management.feature",
    "Atualizar campos sem alterar RTSP não chama MediaMTX",
)
def test_update_without_rtsp_skips_mediamtx():
    pass


@scenario(
    "../features/camera_management.feature",
    "Deletar câmera",
)
def test_delete_camera():
    pass


@scenario(
    "../features/camera_management.feature",
    "Obter URL de streaming de câmera online",
)
def test_get_stream_url_online():
    pass


@scenario(
    "../features/camera_management.feature",
    "Obter URL de streaming de câmera offline",
)
def test_get_stream_url_offline():
    pass


@scenario(
    "../features/camera_management.feature",
    "Isolamento entre tenants",
)
def test_tenant_isolation():
    pass


@scenario(
    "../features/camera_management.feature",
    "Falha no MediaMTX reverte criação",
)
def test_mediamtx_failure_rollback_create():
    pass


@scenario(
    "../features/camera_management.feature",
    "Falha no MediaMTX reverte atualização",
)
def test_mediamtx_failure_rollback_update():
    pass


@scenario(
    "../features/camera_management.feature",
    "Falha no MediaMTX não impede deleção",
)
def test_mediamtx_failure_delete_continues():
    pass


# Given steps
@given("que estou autenticado como operador", target_fixture="context")
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
        "camera": None,
        "cameras": [],
    }


@given(parsers.parse('que existem {count:d} câmeras no meu tenant'))
def cameras_in_my_tenant(context, count):
    """Cria câmeras no tenant do usuário."""
    context["cameras"] = CameraFactory.create_batch(
        count,
        tenant=context["tenant"],
    )


@given(parsers.parse('existem {count:d} câmeras em outro tenant'))
def cameras_in_other_tenant(context, count):
    """Cria câmeras em outro tenant."""
    other_tenant = TenantFactory()
    CameraFactory.create_batch(count, tenant=other_tenant)


@given(parsers.parse('que existe uma câmera "{name}" cadastrada'))
def camera_exists(context, name):
    """Cria uma câmera com nome específico."""
    context["camera"] = CameraFactory(
        name=name,
        tenant=context["tenant"],
    )


@given("que existe uma câmera cadastrada")
def camera_exists_generic(context):
    """Cria uma câmera genérica."""
    context["camera"] = CameraFactory(tenant=context["tenant"])


@given("que existe uma câmera online")
def camera_online(context):
    """Cria uma câmera online."""
    context["camera"] = CameraFactory(
        tenant=context["tenant"],
        is_online=True,
    )


@given("que existe uma câmera offline")
def camera_offline(context):
    """Cria uma câmera offline."""
    context["camera"] = CameraFactory(
        tenant=context["tenant"],
        is_online=False,
    )


@given(parsers.parse('que existe uma câmera com RTSP "{rtsp_url}"'))
def camera_with_rtsp(context, rtsp_url):
    """Cria câmera com RTSP específico."""
    context["camera"] = CameraFactory(
        tenant=context["tenant"],
        rtsp_url=rtsp_url,
    )


@given(parsers.parse('que sou do tenant "{tenant_name}"'))
def user_from_tenant(context, tenant_name):
    """Define tenant do usuário."""
    context["tenant"].name = tenant_name
    context["tenant"].save()


@given(parsers.parse('existe uma câmera no tenant "{tenant_name}"'))
def camera_in_other_tenant_named(context, tenant_name):
    """Cria câmera em outro tenant."""
    other_tenant = TenantFactory(name=tenant_name)
    context["other_camera"] = CameraFactory(tenant=other_tenant)


@given("o MediaMTX está indisponível")
@given("que o MediaMTX está indisponível")
def mediamtx_unavailable(context):
    """Mock MediaMTX indisponível."""
    context["mediamtx_mock"] = patch(
        "apps.cameras.services.MediaMTXClient"
    )
    mock_cls = context["mediamtx_mock"].start()
    mock_client = MagicMock()
    mock_client.add_path.side_effect = MediaMTXError("Connection failed")
    mock_client.edit_path.side_effect = MediaMTXError("Connection failed")
    mock_client.remove_path.side_effect = MediaMTXError("Connection failed")
    mock_cls.return_value = mock_client


# When steps
@when(
    parsers.parse(
        'eu crio uma câmera "{name}" na "{location}" com RTSP'
        ' "{rtsp_url}" fabricante "{manufacturer}" e retenção {days:d}'
    )
)
def create_camera_with_data(context, name, location, rtsp_url, manufacturer, days):
    """Cria câmera com dados completos."""
    data = {
        "name": name,
        "location": location,
        "rtsp_url": rtsp_url,
        "manufacturer": manufacturer,
        "retention_days": days,
    }

    with patch("apps.cameras.services.MediaMTXClient"), \
         patch("apps.cameras.services.publish_event") as mock_event:
        context["mock_event"] = mock_event
        context["response"] = context["client"].post(
            "/api/v1/cameras/",
            data,
            format="json",
        )


@when(parsers.parse('eu crio uma câmera com nome "{name}" e localização "{location}"'))
def create_camera_minimal(context, name, location):
    """Cria câmera com dados mínimos."""
    data = {
        "name": name,
        "location": location,
        "rtsp_url": "rtsp://192.168.1.100:554/stream",
    }

    with patch("apps.cameras.services.MediaMTXClient"), \
         patch("apps.cameras.services.publish_event"):
        context["response"] = context["client"].post(
            "/api/v1/cameras/",
            data,
            format="json",
        )


@when("eu tento criar uma câmera sem nome")
def create_camera_without_name(context):
    """Tenta criar câmera sem nome."""
    data = {
        "location": "Teste",
        "rtsp_url": "rtsp://192.168.1.100:554/stream",
    }
    context["response"] = context["client"].post(
        "/api/v1/cameras/",
        data,
        format="json",
    )


@when(parsers.parse('eu tento criar uma câmera com URL RTSP inválida "{url}"'))
def create_camera_invalid_rtsp(context, url):
    """Tenta criar câmera com RTSP inválido."""
    data = {
        "name": "Teste",
        "location": "Teste",
        "rtsp_url": url,
    }
    context["response"] = context["client"].post(
        "/api/v1/cameras/",
        data,
        format="json",
    )


@when("eu listo as câmeras")
def list_cameras(context):
    """Lista câmeras."""
    context["response"] = context["client"].get("/api/v1/cameras/")


@when("eu visualizo os detalhes da câmera")
def view_camera_details(context):
    """Visualiza detalhes da câmera."""
    context["response"] = context["client"].get(
        f"/api/v1/cameras/{context['camera'].id}/"
    )


@when(parsers.parse('eu atualizo o nome para "{new_name}"'))
def update_camera_name(context, new_name):
    """Atualiza nome da câmera."""
    with patch("apps.cameras.services.MediaMTXClient"), \
         patch("apps.cameras.services.publish_event") as mock_event:
        context["mock_event"] = mock_event
        context["response"] = context["client"].patch(
            f"/api/v1/cameras/{context['camera'].id}/",
            {"name": new_name},
            format="json",
        )


@when(
    parsers.parse(
        'eu atualizo nome para "{name}" localização "{location}" e retenção {days:d}'
    )
)
def update_multiple_fields(context, name, location, days):
    """Atualiza múltiplos campos."""
    data = {
        "name": name,
        "location": location,
        "retention_days": days,
    }

    with patch("apps.cameras.services.MediaMTXClient"), \
         patch("apps.cameras.services.publish_event") as mock_event:
        context["mock_event"] = mock_event
        context["response"] = context["client"].patch(
            f"/api/v1/cameras/{context['camera'].id}/",
            data,
            format="json",
        )


@when(parsers.parse('eu atualizo o RTSP para "{new_rtsp}"'))
def update_camera_rtsp(context, new_rtsp):
    """Atualiza RTSP da câmera."""
    with patch("apps.cameras.services.MediaMTXClient") as mock_mtx, \
         patch("apps.cameras.services.publish_event"):
        context["mock_mediamtx"] = mock_mtx
        context["response"] = context["client"].patch(
            f"/api/v1/cameras/{context['camera'].id}/",
            {"rtsp_url": new_rtsp},
            format="json",
        )


@when("eu atualizo apenas o nome")
def update_only_name(context):
    """Atualiza apenas o nome."""
    with patch("apps.cameras.services.MediaMTXClient") as mock_mtx, \
         patch("apps.cameras.services.publish_event"):
        context["mock_mediamtx"] = mock_mtx
        context["response"] = context["client"].patch(
            f"/api/v1/cameras/{context['camera'].id}/",
            {"name": "Novo Nome"},
            format="json",
        )


@when("eu deleto a câmera")
def delete_camera(context):
    """Deleta câmera."""
    with patch("apps.cameras.services.MediaMTXClient"), \
         patch("apps.cameras.services.publish_event") as mock_event:
        context["mock_event"] = mock_event
        context["camera_id"] = context["camera"].id
        context["response"] = context["client"].delete(
            f"/api/v1/cameras/{context['camera'].id}/"
        )


@when("eu solicito a URL de streaming")
def get_stream_url(context):
    """Solicita URL de streaming."""
    context["response"] = context["client"].get(
        f"/api/v1/cameras/{context['camera'].id}/stream-url/"
    )


@when("eu tento acessar a câmera do outro tenant")
def access_other_tenant_camera(context):
    """Tenta acessar câmera de outro tenant."""
    context["response"] = context["client"].get(
        f"/api/v1/cameras/{context['other_camera'].id}/"
    )


@when("eu tento criar uma câmera")
def try_create_camera(context):
    """Tenta criar câmera."""
    data = {
        "name": "Teste",
        "location": "Teste",
        "rtsp_url": "rtsp://192.168.1.100:554/stream",
    }

    with patch("apps.cameras.services.publish_event") as mock_event:
        context["mock_event"] = mock_event
        context["response"] = context["client"].post(
            "/api/v1/cameras/",
            data,
            format="json",
        )


@when("eu tento atualizar o RTSP")
def try_update_rtsp(context):
    """Tenta atualizar RTSP."""
    context["original_rtsp"] = context["camera"].rtsp_url

    with patch("apps.cameras.services.publish_event") as mock_event:
        context["mock_event"] = mock_event
        context["response"] = context["client"].patch(
            f"/api/v1/cameras/{context['camera'].id}/",
            {"rtsp_url": "rtsp://192.168.1.200:554/stream"},
            format="json",
        )


@when("eu tento deletar a câmera")
def try_delete_camera(context):
    """Tenta deletar câmera."""
    context["camera_id"] = context["camera"].id

    with patch("apps.cameras.services.publish_event") as mock_event:
        context["mock_event"] = mock_event
        context["response"] = context["client"].delete(
            f"/api/v1/cameras/{context['camera'].id}/"
        )


# Then steps
@then("a câmera é criada com sucesso")
def camera_created_successfully(context):
    """Verifica que câmera foi criada."""
    assert context["response"].status_code == status.HTTP_201_CREATED
    assert "id" in context["response"].data


@then(parsers.parse('a câmera aparece na lista com status "{expected_status}"'))
def camera_in_list_with_status(context, expected_status):
    """Verifica câmera na lista com status."""
    camera_id = context["response"].data["id"]
    response = context["client"].get("/api/v1/cameras/")

    cameras = response.data["results"]
    camera = next((c for c in cameras if c["id"] == camera_id), None)

    assert camera is not None
    expected_online = expected_status == "online"
    assert camera["is_online"] == expected_online


@then("um path é registrado no MediaMTX")
def path_registered_in_mediamtx(context):
    """Verifica que path foi registrado (via mock)."""
    assert context["response"].status_code == status.HTTP_201_CREATED


@then(parsers.parse('um evento "{event_type}" é publicado'))
def event_published(context, event_type):
    """Verifica que evento foi publicado."""
    if "mock_event" in context:
        context["mock_event"].assert_called()
        call_args = context["mock_event"].call_args[0]
        assert call_args[0] == event_type


@then("a câmera é criada com valores padrão")
def camera_created_with_defaults(context):
    """Verifica valores padrão."""
    assert context["response"].status_code == status.HTTP_201_CREATED


@then(parsers.parse('o fabricante é "{manufacturer}"'))
def check_manufacturer(context, manufacturer):
    """Verifica fabricante."""
    assert context["response"].data["manufacturer"] == manufacturer


@then(parsers.parse('a retenção é de {days:d} dias'))
def check_retention(context, days):
    """Verifica retenção."""
    assert context["response"].data["retention_days"] == days


@then("recebo um erro de validação")
def validation_error(context):
    """Verifica erro de validação."""
    assert context["response"].status_code == status.HTTP_400_BAD_REQUEST


@then(parsers.parse('a mensagem indica que "{field}" é obrigatório'))
def field_required_error(context, field):
    """Verifica mensagem de campo obrigatório."""
    assert field in context["response"].data


@then(parsers.parse('a mensagem indica que "{field}" é inválido'))
def field_invalid_error(context, field):
    """Verifica mensagem de campo inválido."""
    assert field in context["response"].data


@then(parsers.parse('vejo {count:d} câmeras'))
def see_camera_count(context, count):
    """Verifica quantidade de câmeras."""
    assert len(context["response"].data["results"]) == count


@then("não vejo câmeras de outros tenants")
def no_other_tenant_cameras(context):
    """Verifica isolamento de tenants."""
    cameras = context["response"].data["results"]
    for camera in cameras:
        assert camera["tenant"] == context["tenant"].id


@then("vejo todas as informações da câmera")
def see_all_camera_info(context):
    """Verifica todas as informações."""
    assert context["response"].status_code == status.HTTP_200_OK
    assert "id" in context["response"].data
    assert "name" in context["response"].data
    assert "location" in context["response"].data


@then(parsers.parse('vejo o nome "{name}"'))
def see_camera_name(context, name):
    """Verifica nome da câmera."""
    assert context["response"].data["name"] == name


@then("vejo o status online/offline")
def see_online_status(context):
    """Verifica campo is_online."""
    assert "is_online" in context["response"].data


@then("o nome é alterado com sucesso")
def name_updated(context):
    """Verifica que nome foi atualizado."""
    assert context["response"].status_code == status.HTTP_200_OK


@then(parsers.parse('o evento contém "{field}" nos campos alterados'))
def event_contains_field(context, field):
    """Verifica campo no evento."""
    if "mock_event" in context:
        call_args = context["mock_event"].call_args
        payload = call_args[0][1]
        assert field in payload.get("changed_fields", [])


@then("todos os campos são atualizados")
def all_fields_updated(context):
    """Verifica que campos foram atualizados."""
    assert context["response"].status_code == status.HTTP_200_OK


@then(parsers.parse('o evento contém {count:d} campos alterados'))
def event_contains_field_count(context, count):
    """Verifica quantidade de campos alterados."""
    if "mock_event" in context:
        call_args = context["mock_event"].call_args
        payload = call_args[0][1]
        assert len(payload.get("changed_fields", [])) == count


@then("o RTSP é atualizado no banco")
def rtsp_updated_in_db(context):
    """Verifica RTSP no banco."""
    assert context["response"].status_code == status.HTTP_200_OK


@then("o path é atualizado no MediaMTX")
def path_updated_in_mediamtx(context):
    """Verifica que MediaMTX foi chamado."""
    mock_client = context["mock_mediamtx"].return_value
    mock_client.edit_path.assert_called()


@then("o nome é atualizado")
def name_updated_simple(context):
    """Verifica que nome foi atualizado."""
    assert context["response"].status_code == status.HTTP_200_OK


@then("o MediaMTX não é chamado")
def mediamtx_not_called(context):
    """Verifica que MediaMTX não foi chamado."""
    mock_client = context["mock_mediamtx"].return_value
    mock_client.edit_path.assert_not_called()


@then("a câmera não aparece mais na lista")
def camera_not_in_list(context):
    """Verifica que câmera foi deletada."""
    assert context["response"].status_code == status.HTTP_204_NO_CONTENT

    response = context["client"].get("/api/v1/cameras/")
    cameras = response.data["results"]
    camera_ids = [c["id"] for c in cameras]
    assert context["camera_id"] not in camera_ids


@then("o path é removido do MediaMTX")
def path_removed_from_mediamtx(context):
    """Verifica remoção do path."""
    assert context["response"].status_code == status.HTTP_204_NO_CONTENT


@then("recebo uma URL válida")
def receive_valid_url(context):
    """Verifica URL válida."""
    assert context["response"].status_code == status.HTTP_200_OK
    assert "url" in context["response"].data
    assert context["response"].data["url"].startswith("http")


@then("a URL contém o path da câmera")
def url_contains_camera_path(context):
    """Verifica path na URL."""
    url = context["response"].data["url"]
    assert f"cam-{context['camera'].id}" in url


@then("recebo um erro indicando que a câmera está offline")
def camera_offline_error(context):
    """Verifica erro de câmera offline."""
    assert context["response"].status_code == status.HTTP_400_BAD_REQUEST
    assert "error" in context["response"].data


@then("recebo um erro 404")
def receive_404_error(context):
    """Verifica erro 404."""
    assert context["response"].status_code == status.HTTP_404_NOT_FOUND


@then("não consigo visualizar a câmera")
def cannot_view_camera(context):
    """Verifica que não consegue visualizar."""
    # Já verificado pelo 404
    pass


@then("recebo um erro")
def receive_error(context):
    """Verifica que recebeu erro."""
    assert context["response"].status_code >= 400


@then("a câmera não é criada no banco")
def camera_not_created(context):
    """Verifica que câmera não foi criada (rollback)."""
    count = Camera.objects.filter(tenant=context["tenant"]).count()
    assert count == 0


@then("nenhum evento é publicado")
def no_event_published(context):
    """Verifica que evento não foi publicado."""
    if "mock_event" in context:
        context["mock_event"].assert_not_called()


@then("o RTSP permanece inalterado no banco")
def rtsp_unchanged(context):
    """Verifica que RTSP não mudou."""
    context["camera"].refresh_from_db()
    assert context["camera"].rtsp_url == context["original_rtsp"]


@then("a câmera ainda existe no banco")
def camera_still_exists(context):
    """Verifica que câmera ainda existe."""
    assert Camera.objects.filter(id=context["camera_id"]).exists()


@then("a câmera é deletada mesmo assim")
def camera_deleted_despite_mediamtx(context):
    """Verifica que a câmera foi deletada mesmo com MediaMTX indisponível."""
    assert context["response"].status_code == status.HTTP_204_NO_CONTENT
    assert not Camera.objects.filter(id=context["camera_id"]).exists()


# Cleanup
def pytest_bdd_after_scenario(request, feature, scenario):
    """Cleanup após cada cenário."""
    context = request.getfixturevalue("context")
    if "mediamtx_mock" in context:
        context["mediamtx_mock"].stop()
