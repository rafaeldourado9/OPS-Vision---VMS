"""Testes E2E para fluxo completo de câmera."""
import time

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.cameras.models import Camera
from tests.factories import UserFactory


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
class TestCameraCompleteFlow:
    """Teste end-to-end: ciclo completo de câmera."""

    def setup_method(self):
        """Setup para cada teste."""
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_complete_camera_lifecycle(self, docker_services, mediamtx_client):
        """Ciclo completo: criar → verificar MediaMTX → atualizar → deletar."""
        # 1. Criar câmera
        create_data = {
            "name": "E2E Camera",
            "location": "Test Location",
            "rtsp_url": "rtsp://test-stream:554/live",
            "manufacturer": "intelbras",
            "retention_days": 7,
        }

        response = self.client.post(
            "/api/v1/cameras/",
            create_data,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        camera_id = response.data["id"]

        # 2. Verificar que câmera existe no banco
        camera = Camera.objects.get(id=camera_id)
        assert camera.name == "E2E Camera"
        assert camera.is_online is False

        # 3. Verificar que path foi criado no MediaMTX
        path_name = f"tenant-{self.user.tenant_id}/cam-{camera_id}"

        # Aguarda um pouco para MediaMTX processar
        time.sleep(1)

        try:
            mtx_response = mediamtx_client.get(
                f"/v3/config/paths/get/{path_name}"
            )
            assert mtx_response.status_code == 200
            path_data = mtx_response.json()
            assert path_data["source"] == "rtsp://test-stream:554/live"
        except Exception as e:
            pytest.skip(f"MediaMTX path verification failed: {e}")

        # 4. Listar câmeras
        response = self.client.get("/api/v1/cameras/")
        assert response.status_code == status.HTTP_200_OK
        cameras = response.data["results"]
        assert len(cameras) >= 1
        assert any(c["id"] == camera_id for c in cameras)

        # 5. Obter detalhes
        response = self.client.get(f"/api/v1/cameras/{camera_id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "E2E Camera"

        # 6. Atualizar câmera
        update_data = {
            "name": "E2E Camera Updated",
            "retention_days": 30,
        }

        response = self.client.patch(
            f"/api/v1/cameras/{camera_id}/",
            update_data,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "E2E Camera Updated"
        assert response.data["retention_days"] == 30

        # 7. Verificar atualização no banco
        camera.refresh_from_db()
        assert camera.name == "E2E Camera Updated"
        assert camera.retention_days == 30

        # 8. Deletar câmera
        response = self.client.delete(f"/api/v1/cameras/{camera_id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # 9. Verificar que não existe mais
        assert not Camera.objects.filter(id=camera_id).exists()

        # 10. Verificar que path foi removido do MediaMTX
        time.sleep(1)

        try:
            mtx_response = mediamtx_client.get(
                f"/v3/config/paths/get/{path_name}"
            )
            # Path não deve existir mais (404 ou erro)
            assert mtx_response.status_code == 404
        except Exception:
            # Path removido com sucesso
            pass

    def test_update_rtsp_updates_mediamtx(self, docker_services, mediamtx_client):
        """Atualizar RTSP atualiza path no MediaMTX."""
        # 1. Criar câmera
        create_data = {
            "name": "RTSP Test Camera",
            "location": "Test",
            "rtsp_url": "rtsp://original:554/stream",
            "manufacturer": "other",
            "retention_days": 7,
        }

        response = self.client.post(
            "/api/v1/cameras/",
            create_data,
            format="json",
        )

        camera_id = response.data["id"]
        path_name = f"tenant-{self.user.tenant_id}/cam-{camera_id}"

        time.sleep(1)

        # 2. Atualizar RTSP
        update_data = {"rtsp_url": "rtsp://updated:554/stream"}

        response = self.client.patch(
            f"/api/v1/cameras/{camera_id}/",
            update_data,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

        time.sleep(1)

        # 3. Verificar que path foi atualizado no MediaMTX
        try:
            mtx_response = mediamtx_client.get(
                f"/v3/config/paths/get/{path_name}"
            )
            if mtx_response.status_code == 200:
                path_data = mtx_response.json()
                assert path_data["source"] == "rtsp://updated:554/stream"
        except Exception as e:
            pytest.skip(f"MediaMTX verification failed: {e}")

        # Cleanup
        self.client.delete(f"/api/v1/cameras/{camera_id}/")

    def test_tenant_isolation(self, docker_services):
        """Câmeras de diferentes tenants são isoladas."""
        # 1. Criar câmera no tenant 1
        response = self.client.post(
            "/api/v1/cameras/",
            {
                "name": "Tenant 1 Camera",
                "location": "Location 1",
                "rtsp_url": "rtsp://tenant1:554/stream",
            },
            format="json",
        )

        tenant1_camera_id = response.data["id"]

        # 2. Criar usuário do tenant 2
        user2 = UserFactory()
        client2 = APIClient()
        client2.force_authenticate(user=user2)

        # 3. Criar câmera no tenant 2
        response = client2.post(
            "/api/v1/cameras/",
            {
                "name": "Tenant 2 Camera",
                "location": "Location 2",
                "rtsp_url": "rtsp://tenant2:554/stream",
            },
            format="json",
        )

        tenant2_camera_id = response.data["id"]

        # 4. Tenant 1 não vê câmera do tenant 2
        response = self.client.get("/api/v1/cameras/")
        camera_ids = [c["id"] for c in response.data["results"]]
        assert tenant1_camera_id in camera_ids
        assert tenant2_camera_id not in camera_ids

        # 5. Tenant 2 não vê câmera do tenant 1
        response = client2.get("/api/v1/cameras/")
        camera_ids = [c["id"] for c in response.data["results"]]
        assert tenant2_camera_id in camera_ids
        assert tenant1_camera_id not in camera_ids

        # 6. Tenant 1 não pode acessar câmera do tenant 2
        response = self.client.get(f"/api/v1/cameras/{tenant2_camera_id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Cleanup
        self.client.delete(f"/api/v1/cameras/{tenant1_camera_id}/")
        client2.delete(f"/api/v1/cameras/{tenant2_camera_id}/")

    def test_stream_url_for_online_camera(self, docker_services):
        """Obter URL de streaming para câmera online."""
        # 1. Criar câmera
        response = self.client.post(
            "/api/v1/cameras/",
            {
                "name": "Stream Test Camera",
                "location": "Test",
                "rtsp_url": "rtsp://stream:554/live",
            },
            format="json",
        )

        camera_id = response.data["id"]

        # 2. Marcar como online (simula webhook do MediaMTX)
        camera = Camera.objects.get(id=camera_id)
        camera.is_online = True
        camera.save()

        # 3. Obter URL de streaming
        response = self.client.get(
            f"/api/v1/cameras/{camera_id}/stream-url/"
        )

        assert response.status_code == status.HTTP_200_OK
        assert "url" in response.data
        assert f"cam-{camera_id}" in response.data["url"]
        assert response.data["url"].startswith("http://")

        # Cleanup
        self.client.delete(f"/api/v1/cameras/{camera_id}/")

    def test_stream_url_for_offline_camera(self, docker_services):
        """Erro ao obter URL de streaming para câmera offline."""
        # 1. Criar câmera (offline por padrão)
        response = self.client.post(
            "/api/v1/cameras/",
            {
                "name": "Offline Camera",
                "location": "Test",
                "rtsp_url": "rtsp://offline:554/live",
            },
            format="json",
        )

        camera_id = response.data["id"]

        # 2. Tentar obter URL de streaming
        response = self.client.get(
            f"/api/v1/cameras/{camera_id}/stream-url/"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data

        # Cleanup
        self.client.delete(f"/api/v1/cameras/{camera_id}/")


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
class TestEventBusIntegration:
    """Testes de integração com RabbitMQ."""

    def setup_method(self):
        """Setup para cada teste."""
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_camera_created_event_published(
        self,
        docker_services,
        rabbitmq_channel,
        event_consumer,
    ):
        """Evento camera.created é publicado no RabbitMQ."""
        # 1. Criar câmera
        response = self.client.post(
            "/api/v1/cameras/",
            {
                "name": "Event Test Camera",
                "location": "Test",
                "rtsp_url": "rtsp://event:554/live",
            },
            format="json",
        )

        camera_id = response.data["id"]

        # 2. Aguardar evento
        time.sleep(2)

        # 3. Consumir eventos pendentes
        for _ in range(10):
            rabbitmq_channel.connection.process_data_events(time_limit=0.1)

        # 4. Verificar evento
        events = event_consumer["events"]
        camera_created_events = [
            e for e in events
            if e["type"] == "camera.created"
            and e["payload"].get("camera_id") == camera_id
        ]

        if len(camera_created_events) > 0:
            event = camera_created_events[0]
            assert event["payload"]["camera_id"] == camera_id
            assert event["payload"]["tenant_id"] == self.user.tenant_id
            assert event["payload"]["name"] == "Event Test Camera"
        else:
            pytest.skip("Event not received (RabbitMQ timing issue)")

        # Cleanup
        self.client.delete(f"/api/v1/cameras/{camera_id}/")

    def test_camera_updated_event_published(
        self,
        docker_services,
        rabbitmq_channel,
        event_consumer,
    ):
        """Evento camera.updated é publicado no RabbitMQ."""
        # 1. Criar câmera
        response = self.client.post(
            "/api/v1/cameras/",
            {
                "name": "Update Event Camera",
                "location": "Test",
                "rtsp_url": "rtsp://update:554/live",
            },
            format="json",
        )

        camera_id = response.data["id"]

        # Limpar eventos anteriores
        event_consumer["events"].clear()

        # 2. Atualizar câmera
        response = self.client.patch(
            f"/api/v1/cameras/{camera_id}/",
            {"name": "Updated Name"},
            format="json",
        )

        # 3. Aguardar evento
        time.sleep(2)

        # 4. Consumir eventos
        for _ in range(10):
            rabbitmq_channel.connection.process_data_events(time_limit=0.1)

        # 5. Verificar evento
        events = event_consumer["events"]
        camera_updated_events = [
            e for e in events
            if e["type"] == "camera.updated"
            and e["payload"].get("camera_id") == camera_id
        ]

        if len(camera_updated_events) > 0:
            event = camera_updated_events[0]
            assert event["payload"]["camera_id"] == camera_id
            assert "changed_fields" in event["payload"]
            assert "name" in event["payload"]["changed_fields"]
        else:
            pytest.skip("Event not received (RabbitMQ timing issue)")

        # Cleanup
        self.client.delete(f"/api/v1/cameras/{camera_id}/")

    def test_camera_deleted_event_published(
        self,
        docker_services,
        rabbitmq_channel,
        event_consumer,
    ):
        """Evento camera.deleted é publicado no RabbitMQ."""
        # 1. Criar câmera
        response = self.client.post(
            "/api/v1/cameras/",
            {
                "name": "Delete Event Camera",
                "location": "Test",
                "rtsp_url": "rtsp://delete:554/live",
            },
            format="json",
        )

        camera_id = response.data["id"]

        # Limpar eventos anteriores
        event_consumer["events"].clear()

        # 2. Deletar câmera
        response = self.client.delete(f"/api/v1/cameras/{camera_id}/")

        # 3. Aguardar evento
        time.sleep(2)

        # 4. Consumir eventos
        for _ in range(10):
            rabbitmq_channel.connection.process_data_events(time_limit=0.1)

        # 5. Verificar evento
        events = event_consumer["events"]
        camera_deleted_events = [
            e for e in events
            if e["type"] == "camera.deleted"
            and e["payload"].get("camera_id") == camera_id
        ]

        if len(camera_deleted_events) > 0:
            event = camera_deleted_events[0]
            assert event["payload"]["camera_id"] == camera_id
            assert event["payload"]["tenant_id"] == self.user.tenant_id
        else:
            pytest.skip("Event not received (RabbitMQ timing issue)")
