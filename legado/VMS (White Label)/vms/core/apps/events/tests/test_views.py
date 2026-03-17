from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import CameraFactory, EventFactory, TenantFactory, UserFactory


@pytest.fixture
def auth_client():
    client = APIClient()
    user = UserFactory()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
class TestEventViewSet:
    def test_list_events_tenant_isolation(self, auth_client):
        """Valida que o usuário só vê eventos do seu próprio tenant."""
        client, user = auth_client

        # Evento do tenant logado
        own_camera = CameraFactory(tenant=user.tenant)
        own_event = EventFactory(camera=own_camera)

        # Evento de outro tenant
        other_tenant = TenantFactory()
        other_camera = CameraFactory(tenant=other_tenant)
        EventFactory(camera=other_camera)

        url = reverse("event-list")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == own_event.id

    def test_detail_view_tenant_isolation(self, auth_client):
        """Valida 404 ao tentar acessar detalhe de evento de outro tenant."""
        client, _ = auth_client
        other_event = EventFactory()

        url = reverse("event-detail", args=[other_event.id])
        response = client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_filter_by_camera(self, auth_client):
        """Valida filtro ?camera_id=..."""
        client, user = auth_client
        cam1 = CameraFactory(tenant=user.tenant)
        cam2 = CameraFactory(tenant=user.tenant)

        ev1 = EventFactory(camera=cam1)
        EventFactory(camera=cam2)

        url = reverse("event-list")
        response = client.get(f"{url}?camera_id={cam1.id}")

        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == ev1.id

    def test_filter_by_event_type(self, auth_client):
        """Valida filtro ?event_type=..."""
        client, user = auth_client
        cam = CameraFactory(tenant=user.tenant)

        ev1 = EventFactory(camera=cam, event_type="alpr.detected")
        EventFactory(camera=cam, event_type="camera.offline")

        url = reverse("event-list")
        response = client.get(f"{url}?event_type=alpr.detected")

        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == ev1.id

    def test_filter_by_date_range(self, auth_client):
        """Valida filtros ?created_from=... e ?created_to=..."""
        client, user = auth_client
        cam = CameraFactory(tenant=user.tenant)

        now = timezone.now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)

        # Cria eventos com datas forçadas (criando objects.create pq auto_now_add ignora)
        ev_yesterday = EventFactory(camera=cam)
        ev_yesterday.created_at = yesterday
        ev_yesterday.save()

        ev_now = EventFactory(camera=cam)
        ev_now.created_at = now
        ev_now.save()

        ev_tomorrow = EventFactory(camera=cam)
        ev_tomorrow.created_at = tomorrow
        ev_tomorrow.save()

        url = reverse("event-list")

        import urllib.parse
        d_from = urllib.parse.quote(yesterday.isoformat())
        d_to = urllib.parse.quote(now.isoformat())

        response = client.get(f"{url}?created_from={d_from}&created_to={d_to}")

        assert response.data["count"] == 2
        ids = [r["id"] for r in response.data["results"]]
        assert ev_yesterday.id in ids
        assert ev_now.id in ids
        assert ev_tomorrow.id not in ids

    def test_filter_by_confidence(self, auth_client):
        """Valida filtros de plate confidence."""
        client, user = auth_client
        cam = CameraFactory(tenant=user.tenant)

        ev_high = EventFactory(camera=cam, confidence=0.95)
        ev_mid = EventFactory(camera=cam, confidence=0.75)
        EventFactory(camera=cam, confidence=0.50)

        url = reverse("event-list")
        response = client.get(f"{url}?confidence_gte=0.70")

        assert response.data["count"] == 2
        ids = [r["id"] for r in response.data["results"]]
        assert ev_high.id in ids
        assert ev_mid.id in ids

        response2 = client.get(f"{url}?confidence_lte=0.80")
        assert response2.data["count"] == 2  # 0.75 and 0.50

    def test_filter_by_plate(self, auth_client):
        """Valida filtro exato e parcial por placa."""
        client, user = auth_client
        cam = CameraFactory(tenant=user.tenant)

        ev1 = EventFactory(camera=cam, plate="ABC1234")
        ev2 = EventFactory(camera=cam, plate="XYZ9876")

        url = reverse("event-list")

        # Exact match
        r_exact = client.get(f"{url}?plate=ABC1234")
        assert r_exact.data["count"] == 1
        assert r_exact.data["results"][0]["id"] == ev1.id

        # icontains match
        r_partial = client.get(f"{url}?plate__icontains=xyz")
        assert r_partial.data["count"] == 1
        assert r_partial.data["results"][0]["id"] == ev2.id

    def test_pagination_max_size(self, auth_client):
        """Valida restrição de página."""
        client, user = auth_client
        cam = CameraFactory(tenant=user.tenant)

        # Create 15 events
        for _ in range(15):
            EventFactory(camera=cam)

        url = reverse("event-list")

        # Even if asked for 1000, should limit to 100
        # But we only generated 15, let's test page_size=10 works
        r_page10 = client.get(f"{url}?page_size=10")
        assert r_page10.data["count"] == 15
        assert len(r_page10.data["results"]) == 10
        assert r_page10.data["next"] is not None
