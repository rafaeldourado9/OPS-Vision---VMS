"""Testes para API de reconhecimento facial — FaceProfile e FaceDetectionEvent."""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.analytics.models import FaceDetectionEvent, FaceProfile, RegionOfInterest
from tests.factories import CameraFactory, TenantFactory, UserFactory

FAKE_EMBEDDING = [0.1] * 512


@pytest.fixture()
def client_auth():
    """Cliente autenticado com tenant sem facial recognition habilitado."""
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.fixture()
def client_face_enabled():
    """Cliente autenticado com facial_recognition_enabled=True no tenant."""
    from django.utils import timezone
    user = UserFactory()
    tenant = user.tenant
    tenant.facial_recognition_enabled = True
    tenant.facial_recognition_consent_at = timezone.now()
    tenant.save()
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


# ── FaceProfile ────────────────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.django_db
class TestFaceProfileViewSet:
    """Testes do CRUD de FaceProfile."""

    def test_list_returns_only_tenant_profiles(self, client_face_enabled):
        """Lista somente perfis do tenant do usuário."""
        client, user = client_face_enabled
        FaceProfile.objects.create(
            name="João",
            embedding=FAKE_EMBEDDING,
            lgpd_consent=True,
            tenant=user.tenant,
        )
        other_tenant = TenantFactory()
        FaceProfile.objects.create(
            name="Maria",
            embedding=FAKE_EMBEDDING,
            lgpd_consent=True,
            tenant=other_tenant,
        )

        response = client.get("/api/v1/analytics/face-profiles/")

        assert response.status_code == status.HTTP_200_OK
        names = [p["name"] for p in response.data["results"]]
        assert "João" in names
        assert "Maria" not in names

    def test_create_profile_success(self, client_face_enabled):
        """Criação com lgpd_consent=True e tenant habilitado retorna 201."""
        client, user = client_face_enabled

        response = client.post("/api/v1/analytics/face-profiles/", {
            "name": "Carlos",
            "cpf": "12345678901",
            "lgpd_consent": True,
            "embedding": FAKE_EMBEDDING,
        }, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Carlos"
        assert response.data["cpf"] == "123.456.789-01"
        assert "embedding" not in response.data  # write-only

    def test_create_blocked_when_facial_recognition_disabled(self, client_auth):
        """Criação bloqueada quando tenant.facial_recognition_enabled=False."""
        client, user = client_auth

        response = client.post("/api/v1/analytics/face-profiles/", {
            "name": "Bloqueado",
            "lgpd_consent": True,
            "embedding": FAKE_EMBEDDING,
        }, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_blocked_without_lgpd_consent(self, client_face_enabled):
        """Criação bloqueada quando lgpd_consent=False."""
        client, user = client_face_enabled

        response = client.post("/api/v1/analytics/face-profiles/", {
            "name": "Sem Consent",
            "lgpd_consent": False,
            "embedding": FAKE_EMBEDDING,
        }, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_by_cpf(self, client_face_enabled):
        """DELETE /by-cpf/ remove todos os perfis do CPF (direito ao esquecimento LGPD)."""
        client, user = client_face_enabled
        cpf = "123.456.789-01"
        FaceProfile.objects.create(name="P1", cpf=cpf, embedding=FAKE_EMBEDDING, lgpd_consent=True, tenant=user.tenant)
        FaceProfile.objects.create(name="P2", cpf=cpf, embedding=FAKE_EMBEDDING, lgpd_consent=True, tenant=user.tenant)
        FaceProfile.objects.create(name="P3", cpf="999.999.999-99", embedding=FAKE_EMBEDDING, lgpd_consent=True, tenant=user.tenant)

        response = client.delete(f"/api/v1/analytics/face-profiles/by-cpf/?cpf={cpf}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["deleted"] == 2
        assert FaceProfile.objects.filter(tenant=user.tenant).count() == 1

    def test_delete_by_cpf_missing_param(self, client_face_enabled):
        """Retorna 400 se cpf não informado."""
        client, _ = client_face_enabled
        response = client.delete("/api/v1/analytics/face-profiles/by-cpf/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_by_cpf_does_not_affect_other_tenant(self, client_face_enabled):
        """DELETE por CPF não afeta perfis de outro tenant."""
        client, user = client_face_enabled
        cpf = "123.456.789-01"
        other_tenant = TenantFactory()
        FaceProfile.objects.create(name="Outro", cpf=cpf, embedding=FAKE_EMBEDDING, lgpd_consent=True, tenant=other_tenant)

        response = client.delete(f"/api/v1/analytics/face-profiles/by-cpf/?cpf={cpf}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["deleted"] == 0
        assert FaceProfile.objects.filter(tenant=other_tenant, cpf=cpf).count() == 1

    def test_embedding_is_write_only(self, client_face_enabled):
        """Embedding não aparece na resposta (dado biométrico)."""
        client, user = client_face_enabled
        profile = FaceProfile.objects.create(
            name="Embed Test",
            embedding=FAKE_EMBEDDING,
            lgpd_consent=True,
            tenant=user.tenant,
        )

        response = client.get(f"/api/v1/analytics/face-profiles/{profile.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert "embedding" not in response.data

    def test_cpf_invalid_format(self, client_face_enabled):
        """CPF com número errado de dígitos retorna 400."""
        client, _ = client_face_enabled
        response = client.post("/api/v1/analytics/face-profiles/", {
            "name": "Inválido",
            "cpf": "123",
            "lgpd_consent": True,
            "embedding": FAKE_EMBEDDING,
        }, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ── LGPD Consent ──────────────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.django_db
class TestFaceRecognitionConsent:
    """Testes do endpoint LGPD consent."""

    def test_accept_consent_enables_facial_recognition(self, client_auth):
        """PATCH com confirm=true habilita reconhecimento facial no tenant."""
        client, user = client_auth
        assert not user.tenant.facial_recognition_enabled

        response = client.patch(
            "/api/v1/analytics/face-recognition/consent/",
            {"confirm": True},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["facial_recognition_enabled"] is True
        user.tenant.refresh_from_db()
        assert user.tenant.facial_recognition_enabled is True
        assert user.tenant.facial_recognition_consent_at is not None

    def test_consent_without_confirm_returns_400(self, client_auth):
        """PATCH sem confirm=true retorna 400."""
        client, _ = client_auth
        response = client.patch(
            "/api/v1/analytics/face-recognition/consent/",
            {"confirm": False},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_consent_requires_authentication(self):
        """Endpoint requer autenticação."""
        client = APIClient()
        response = client.patch(
            "/api/v1/analytics/face-recognition/consent/",
            {"confirm": True},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── FaceDetectionEvent ─────────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.django_db
class TestFaceDetectionEventViewSet:
    """Testes de leitura de FaceDetectionEvent."""

    def test_list_returns_only_tenant_events(self, client_face_enabled):
        """Lista somente eventos do tenant do usuário."""
        client, user = client_face_enabled
        camera = CameraFactory(tenant=user.tenant)
        other_tenant = TenantFactory()
        other_camera = CameraFactory(tenant=other_tenant)

        FaceDetectionEvent.objects.create(
            camera=camera, tenant=user.tenant, is_unknown=True, confidence=0.0
        )
        FaceDetectionEvent.objects.create(
            camera=other_camera, tenant=other_tenant, is_unknown=True, confidence=0.0
        )

        response = client.get("/api/v1/analytics/face-events/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_by_camera(self, client_face_enabled):
        """Filtro por camera_id funciona."""
        client, user = client_face_enabled
        cam1 = CameraFactory(tenant=user.tenant)
        cam2 = CameraFactory(tenant=user.tenant)
        FaceDetectionEvent.objects.create(camera=cam1, tenant=user.tenant, is_unknown=True, confidence=0.0)
        FaceDetectionEvent.objects.create(camera=cam2, tenant=user.tenant, is_unknown=True, confidence=0.0)

        response = client.get(f"/api/v1/analytics/face-events/?camera={cam1.id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_by_is_unknown(self, client_face_enabled):
        """Filtro is_unknown=true retorna apenas desconhecidos."""
        client, user = client_face_enabled
        camera = CameraFactory(tenant=user.tenant)
        profile = FaceProfile.objects.create(
            name="Conhecido", embedding=FAKE_EMBEDDING, lgpd_consent=True, tenant=user.tenant
        )
        FaceDetectionEvent.objects.create(
            camera=camera, tenant=user.tenant, face_profile=profile, is_unknown=False, confidence=0.85
        )
        FaceDetectionEvent.objects.create(
            camera=camera, tenant=user.tenant, is_unknown=True, confidence=0.0
        )

        response = client.get("/api/v1/analytics/face-events/?is_unknown=true")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["is_unknown"] is True

    def test_create_is_forbidden(self, client_face_enabled):
        """POST em face-events retorna 405 (somente leitura)."""
        client, _ = client_face_enabled
        response = client.post("/api/v1/analytics/face-events/", {}, format="json")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
