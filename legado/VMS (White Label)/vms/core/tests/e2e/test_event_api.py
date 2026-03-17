"""Testes E2E para a API de Event Query."""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import CameraFactory, EventFactory, UserFactory


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
class TestEventAPICompleteFlow:
    """Teste end-to-end: ciclo completo de consulta de eventos na API."""

    def setup_method(self):
        """Setup base para isolamento multi-tenant E2E."""
        self.client_1 = APIClient()
        self.user_1 = UserFactory(username="e2e_user1")
        self.client_1.force_authenticate(user=self.user_1)

        self.client_2 = APIClient()
        self.user_2 = UserFactory(username="e2e_user2")
        self.client_2.force_authenticate(user=self.user_2)

    def test_complete_event_query_lifecycle(self, docker_services):
        """Ciclo de criação e consulta mista com filtros."""

        # 1. Setup Data for Tenant 1
        cam_1 = CameraFactory(tenant=self.user_1.tenant, name="T1 Camera Front")

        # Event 1: ALPR High Confidence
        EventFactory(
            camera=cam_1,
            event_type="alpr.detected",
            plate="E2E1234",
            confidence=0.98,
        )

        # Event 2: ALPR Low Confidence
        EventFactory(
            camera=cam_1,
            event_type="alpr.detected",
            plate="E2E9876",
            confidence=0.65,
        )

        # Event 3: Different Type
        EventFactory(
            camera=cam_1,
            event_type="camera.offline",
        )

        # 2. Setup Data for Tenant 2
        cam_2 = CameraFactory(tenant=self.user_2.tenant, name="T2 Camera Back")
        EventFactory(
            camera=cam_2,
            event_type="alpr.detected",
            plate="T2P0000",
            confidence=0.99,
        )

        # 3. Tenant 1 Queries everything
        response = self.client_1.get("/api/v1/events/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["count"] == 3

        # 4. Tenant 2 Queries everything
        response_t2 = self.client_2.get("/api/v1/events/")
        assert response_t2.status_code == status.HTTP_200_OK
        assert response_t2.data["count"] == 1
        assert response_t2.data["results"][0]["plate"] == "T2P0000"

        # 5. Tenant 1 Filters by ALPR
        response = self.client_1.get("/api/v1/events/?event_type=alpr.detected")
        assert response.data["count"] == 2

        # 6. Tenant 1 Filters by High Confidence
        response = self.client_1.get("/api/v1/events/?confidence_gte=0.95")
        assert response.data["count"] == 1
        assert response.data["results"][0]["plate"] == "E2E1234"

        # 7. Tenant 1 Filters by Partial Plate
        response = self.client_1.get("/api/v1/events/?plate__icontains=9876")
        assert response.data["count"] == 1
        assert response.data["results"][0]["plate"] == "E2E9876"

        # 8. Detail View isolation (Tenant 1 tries to read Tenant 2 event)
        t2_event_id = response_t2.data["results"][0]["id"]
        response_404 = self.client_1.get(f"/api/v1/events/{t2_event_id}/")
        assert response_404.status_code == status.HTTP_404_NOT_FOUND
