import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from rest_framework import status
from rest_framework.test import APIClient

from apps.cameras.models import Camera
from apps.events.models import Event
from tests.factories import CameraFactory, EventFactory, TenantFactory, UserFactory

pytestmark = [pytest.mark.bdd, pytest.mark.django_db]

scenarios("../features/event_query.feature")


@given(parsers.parse('an authenticated user "{username}" for tenant "{tenant_slug}"'), target_fixture="auth_client")
def auth_user(username, tenant_slug):
    tenant = TenantFactory(slug=tenant_slug, name=tenant_slug.capitalize())
    user = UserFactory(username=username, tenant=tenant)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@given(parsers.parse('the tenant "{tenant_slug}" has a camera "{camera_name}"'))
def tenant_camera(tenant_slug, camera_name):
    tenant = TenantFactory(slug=tenant_slug, name=tenant_slug.capitalize())
    CameraFactory(tenant=tenant, name=camera_name)


@given(parsers.parse('an ALPR event exists for "{camera_name}" with plate "{plate}" and confidence {confidence:f}'))
def alpr_event_exists(camera_name, plate, confidence):
    camera = Camera.objects.get(name=camera_name)
    EventFactory(
        camera=camera,
        event_type="alpr.detected",
        plate=plate,
        confidence=confidence
    )


@when('the user requests the list of events', target_fixture="event_response")
def request_list_events(auth_client):
    return auth_client.get("/api/v1/events/")


@when(parsers.parse('the user filters events with "{filter_name1}" set to "{filter_val1}" and "{filter_name2}" set to "{filter_val2}"'), target_fixture="event_response")
def filter_events_multiple(auth_client, filter_name1, filter_val1, filter_name2, filter_val2):
    return auth_client.get(f"/api/v1/events/?{filter_name1}={filter_val1}&{filter_name2}={filter_val2}")


@then(parsers.re(r'^the response should contain (?P<count>\d+) events?$'))
def response_count(event_response, count):
    assert event_response.status_code == status.HTTP_200_OK
    results = event_response.data if isinstance(event_response.data, list) else event_response.data.get("results", [])
    assert len(results) == int(count)


@then(parsers.parse('all returned events should belong to "{tenant_slug}"'))
def returned_events_belong_to(event_response, tenant_slug):
    results = event_response.data if isinstance(event_response.data, list) else event_response.data.get("results", [])
    for result in results:
        event = Event.objects.get(id=result["id"])
        assert event.tenant.slug == tenant_slug


@then(parsers.parse('the plate "{plate}" should not be in the response'))
def plate_not_in_response(event_response, plate):
    results = event_response.data if isinstance(event_response.data, list) else event_response.data.get("results", [])
    plates = [r.get("plate", "") for r in results]
    assert plate not in plates


@then(parsers.parse('the returned event should have plate "{plate}"'))
def returned_event_has_plate(event_response, plate):
    results = event_response.data if isinstance(event_response.data, list) else event_response.data.get("results", [])
    assert results[0]["plate"] == plate
