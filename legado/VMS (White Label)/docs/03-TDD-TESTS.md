# 03 — GT-Vision · Plano de Testes TDD
**Test-Driven Development — Backend Django + FastAPI · v1.0**

---

## 1. Estratégia de Testes

### Pirâmide de Testes
```
         /\
        /E2E\          → 10% — Cypress (fluxos críticos do usuário)
       /──────\
      /Integração\     → 30% — pytest + Django test client
     /────────────\
    / Unit Tests   \   → 60% — pytest puro, sem banco, sem rede
   /────────────────\
```

### Ferramentas
- **Backend Django:** `pytest-django`, `factory_boy`, `faker`, `pytest-cov`
- **Backend FastAPI:** `pytest`, `httpx`, `pytest-asyncio`
- **Frontend:** `Vitest`, `Vue Test Utils` / `React Testing Library`
- **E2E:** `Cypress`

### Cobertura Mínima
- Unit: **90%**
- Integração: **80%**
- E2E: fluxos críticos cobertos

---

## 2. Testes de White Label

### 2.1 Resolução de Tenant por Host
```python
# tests/test_middleware_tenant.py

import pytest
from django.test import RequestFactory
from apps.tenants.models import Tenant
from apps.resellers.models import Reseller
from middleware.tenant import TenantMiddleware

@pytest.fixture
def reseller(db):
    return Reseller.objects.create(
        name="Cidade Segura",
        slug="cidadesegura",
        custom_domain="app.cidadesegura.com.br",
        primary_color="#005A9C",
        active=True
    )

@pytest.fixture
def tenant(db, reseller):
    return Tenant.objects.create(
        reseller=reseller,
        name="São Paulo",
        subdomain="saopaulo",
        active=True
    )

class TestTenantMiddleware:
    def test_resolve_tenant_from_custom_domain(self, tenant, reseller):
        """Deve resolver tenant e reseller pelo custom domain do reseller."""
        factory = RequestFactory()
        request = factory.get("/", HTTP_HOST="app.cidadesegura.com.br")
        middleware = TenantMiddleware(get_response=lambda r: r)
        middleware(request)
        assert request.reseller == reseller
        assert request.tenant is None  # domínio raiz não tem tenant direto

    def test_resolve_tenant_from_subdomain(self, tenant, reseller):
        """Deve resolver tenant pelo subdomínio."""
        factory = RequestFactory()
        request = factory.get("/", HTTP_HOST="saopaulo.cidadesegura.com.br")
        middleware = TenantMiddleware(get_response=lambda r: r)
        middleware(request)
        assert request.tenant == tenant
        assert request.reseller == reseller

    def test_unknown_host_returns_404(self):
        """Host desconhecido deve retornar 404."""
        factory = RequestFactory()
        request = factory.get("/", HTTP_HOST="unknown.example.com")
        middleware = TenantMiddleware(get_response=lambda r: r)
        response = middleware(request)
        assert response.status_code == 404

    def test_white_label_config_cached_in_redis(self, tenant, reseller, redis_mock):
        """Configuração white label deve ser cacheada no Redis."""
        factory = RequestFactory()
        request = factory.get("/", HTTP_HOST="saopaulo.cidadesegura.com.br")
        middleware = TenantMiddleware(get_response=lambda r: r)
        middleware(request)
        middleware(request)  # segunda chamada deve usar cache
        assert redis_mock.get.call_count == 2
        assert redis_mock.set.call_count == 1  # só setou uma vez
```

### 2.2 API de Tema White Label
```python
# tests/test_api_theme.py

class TestThemeAPI:
    def test_returns_reseller_theme(self, client, reseller):
        """GET /api/v1/theme deve retornar cores e logo do revendedor."""
        response = client.get(
            "/api/v1/theme/",
            HTTP_HOST="saopaulo.cidadesegura.com.br"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["primary_color"] == "#005A9C"
        assert "logo_url" in data
        assert "favicon_url" in data

    def test_theme_does_not_expose_fabricante(self, client, reseller):
        """Resposta não deve conter referência ao GT-Vision."""
        response = client.get("/api/v1/theme/", HTTP_HOST="saopaulo.cidadesegura.com.br")
        content = response.content.decode()
        assert "gt-vision" not in content.lower()
        assert "GT-Vision" not in content
```

---

## 3. Testes de Autenticação

```python
# tests/test_auth.py

class TestLogin:
    def test_valid_login_returns_tokens(self, client, user):
        response = client.post("/api/v1/auth/login/", {
            "email": user.email,
            "password": "senha_teste_123"
        })
        assert response.status_code == 200
        assert "access" in response.json()
        assert "refresh" in response.json()

    def test_invalid_password_returns_401(self, client, user):
        response = client.post("/api/v1/auth/login/", {
            "email": user.email,
            "password": "errada"
        })
        assert response.status_code == 401

    def test_account_locked_after_5_failures(self, client, user):
        for _ in range(5):
            client.post("/api/v1/auth/login/", {
                "email": user.email, "password": "errada"
            })
        response = client.post("/api/v1/auth/login/", {
            "email": user.email, "password": "senha_teste_123"
        })
        assert response.status_code == 423  # Locked

    def test_cross_tenant_login_blocked(self, client, user_tenant_a, tenant_b_host):
        """Usuário de tenant A não pode logar em tenant B."""
        response = client.post(
            "/api/v1/auth/login/",
            {"email": user_tenant_a.email, "password": "senha_teste_123"},
            HTTP_HOST=tenant_b_host
        )
        assert response.status_code == 401
```

---

## 4. Testes de Multi-Tenant (Isolamento)

```python
# tests/test_tenant_isolation.py

class TestTenantIsolation:
    def test_camera_not_visible_to_other_tenant(
        self, auth_client_a, camera_tenant_b
    ):
        """Câmera do tenant B não deve aparecer para usuário do tenant A."""
        response = auth_client_a.get("/api/v1/cameras/")
        ids = [c["id"] for c in response.json()["results"]]
        assert str(camera_tenant_b.id) not in ids

    def test_cannot_access_other_tenant_camera_directly(
        self, auth_client_a, camera_tenant_b
    ):
        response = auth_client_a.get(f"/api/v1/cameras/{camera_tenant_b.id}/")
        assert response.status_code == 404

    def test_ai_events_isolated_by_tenant(
        self, auth_client_a, event_tenant_a, event_tenant_b
    ):
        response = auth_client_a.get("/api/v1/detections/")
        ids = [e["id"] for e in response.json()["results"]]
        assert str(event_tenant_a.id) in ids
        assert str(event_tenant_b.id) not in ids

    def test_clips_isolated_by_tenant(
        self, auth_client_a, clip_tenant_a, clip_tenant_b
    ):
        response = auth_client_a.get("/api/v1/clips/")
        ids = [c["id"] for c in response.json()["results"]]
        assert str(clip_tenant_a.id) in ids
        assert str(clip_tenant_b.id) not in ids
```

---

## 5. Testes de Câmeras

```python
# tests/test_cameras.py

class TestCameraCreate:
    def test_create_rtsp_camera(self, auth_admin_client):
        response = auth_admin_client.post("/api/v1/cameras/", {
            "name": "Câmera Centro 01",
            "address": "Av. Paulista, 1000",
            "latitude": -23.5614,
            "longitude": -46.6558,
            "stream_protocol": "rtsp",
            "stream_url": "rtsp://192.168.1.100:554/stream",
            "retention_days": 15
        })
        assert response.status_code == 201
        assert response.json()["ia_status"] == "disabled"

    def test_create_rtmp_camera_generates_stream_key(self, auth_admin_client):
        response = auth_admin_client.post("/api/v1/cameras/", {
            "name": "Câmera RTMP 01",
            "stream_protocol": "rtmp",
            "retention_days": 7
        })
        assert response.status_code == 201
        assert response.json()["stream_key"] is not None
        assert len(response.json()["stream_key"]) >= 16

    def test_enable_ia_sets_ia_pending(self, auth_admin_client, camera):
        response = auth_admin_client.patch(
            f"/api/v1/cameras/{camera.id}/",
            {"ia_enabled": True}
        )
        assert response.status_code == 200
        assert response.json()["ia_status"] == "ia_pending"

    def test_camera_limit_enforced_by_license(self, auth_admin_client, tenant_at_limit):
        """Não deve criar câmera se tenant atingiu limite da licença."""
        response = auth_admin_client.post("/api/v1/cameras/", {
            "name": "Extra", "stream_protocol": "rtsp",
            "stream_url": "rtsp://...", "retention_days": 7
        })
        assert response.status_code == 403
        assert "limite" in response.json()["detail"].lower()

    def test_operator_cannot_create_camera(self, auth_operator_client):
        response = auth_operator_client.post("/api/v1/cameras/", {
            "name": "Não permitida"
        })
        assert response.status_code == 403
```

---

## 6. Testes de ROI

```python
# tests/test_roi.py

class TestROI:
    def test_create_roi_on_ia_pending_camera(self, auth_supervisor_client, ia_pending_camera):
        response = auth_supervisor_client.post("/api/v1/roi/", {
            "camera_id": str(ia_pending_camera.id),
            "name": "Entrada Principal",
            "polygon": [[10, 20], [200, 20], [200, 300], [10, 300]],
            "ia_type": "lpr"
        })
        assert response.status_code == 201
        ia_pending_camera.refresh_from_db()
        assert ia_pending_camera.ia_status == "active"

    def test_roi_polygon_must_have_minimum_3_points(self, auth_supervisor_client, camera):
        response = auth_supervisor_client.post("/api/v1/roi/", {
            "camera_id": str(camera.id),
            "name": "Inválido",
            "polygon": [[10, 20], [100, 20]],
            "ia_type": "lpr"
        })
        assert response.status_code == 400

    def test_delete_last_roi_sets_ia_pending(self, auth_supervisor_client, camera_with_roi):
        camera, roi = camera_with_roi
        response = auth_supervisor_client.delete(f"/api/v1/roi/{roi.id}/")
        assert response.status_code == 204
        camera.refresh_from_db()
        assert camera.ia_status == "ia_pending"
```

---

## 7. Testes de Gravação e Clipes

```python
# tests/test_recordings.py

class TestSegmentPurge:
    def test_segments_respect_retention_expires_at(self, db):
        camera = CameraFactory(retention_days=7)
        segment = RecordingSegmentFactory(
            camera=camera,
            started_at=datetime.now() - timedelta(days=8)
        )
        assert segment.expires_at < datetime.now()

    def test_purge_deletes_expired_only(self, db, storage_mock):
        expired = RecordingSegmentFactory(expires_at=datetime.now() - timedelta(hours=1))
        active = RecordingSegmentFactory(expires_at=datetime.now() + timedelta(days=5))
        from workers.purge.tasks import run_purge
        run_purge(tenant_id=expired.tenant_id)
        assert not RecordingSegment.objects.filter(id=expired.id).exists()
        assert RecordingSegment.objects.filter(id=active.id).exists()

    def test_manual_clip_never_purged(self, db):
        clip = ClipFactory(created_at=datetime.now() - timedelta(days=100))
        from workers.purge.tasks import run_purge
        run_purge(tenant_id=clip.tenant_id)
        assert Clip.objects.filter(id=clip.id).exists()


class TestClipGeneration:
    def test_clip_request_publishes_to_rabbitmq(self, auth_client, camera, rmq_mock):
        response = auth_client.post("/api/v1/clips/", {
            "camera_id": str(camera.id),
            "started_at": "2024-01-15T10:00:00Z",
            "ended_at": "2024-01-15T10:05:00Z"
        })
        assert response.status_code == 202
        assert rmq_mock.publish.called
        assert rmq_mock.publish.call_args[0][0] == "clip.request"

    def test_clip_status_starts_as_processing(self, auth_client, camera):
        response = auth_client.post("/api/v1/clips/", {
            "camera_id": str(camera.id),
            "started_at": "2024-01-15T10:00:00Z",
            "ended_at": "2024-01-15T10:05:00Z"
        })
        clip_id = response.json()["id"]
        status_response = auth_client.get(f"/api/v1/clips/{clip_id}/")
        assert status_response.json()["status"] == "processing"
```

---

## 8. Testes FastAPI Workers

```python
# workers/recorder/tests/test_recorder.py
import pytest
from unittest.mock import AsyncMock, patch
from workers.recorder.service import RecorderService

class TestRecorderService:
    @pytest.mark.asyncio
    async def test_recorder_creates_segment_metadata(self, db_session, camera_config):
        service = RecorderService(camera_config)
        with patch("workers.recorder.service.ffmpeg_segment") as mock_ffmpeg:
            mock_ffmpeg.return_value = AsyncMock(return_value="/storage/seg_001.mp4")
            await service.record_segment()
        segment = await db_session.get_segment(camera_config.camera_id)
        assert segment is not None
        assert segment.file_path.endswith(".mp4")

    @pytest.mark.asyncio
    async def test_recorder_reconnects_on_stream_failure(self, camera_config):
        service = RecorderService(camera_config)
        service.connect = AsyncMock(side_effect=[ConnectionError, None])
        await service.start_with_retry(max_retries=2)
        assert service.connect.call_count == 2


# workers/ai_worker/tests/test_lpr.py
class TestLPRWorker:
    def test_lpr_detects_plate_in_roi(self, frame_with_plate, roi_polygon):
        from workers.ai_worker.lpr import LPRProcessor
        processor = LPRProcessor()
        result = processor.process(frame_with_plate, roi=roi_polygon)
        assert result is not None
        assert "plate" in result
        assert result["confidence"] > 0.7

    def test_lpr_ignores_plate_outside_roi(self, frame_with_plate_outside_roi, roi_polygon):
        from workers.ai_worker.lpr import LPRProcessor
        processor = LPRProcessor()
        result = processor.process(frame_with_plate_outside_roi, roi=roi_polygon)
        assert result is None
```

---

## 9. Testes de Franquia / Licença

```python
# tests/test_franchise.py

class TestLicense:
    def test_super_admin_creates_reseller(self, super_admin_client):
        response = super_admin_client.post("/master/api/resellers/", {
            "name": "Nova Revenda",
            "slug": "novarevenda",
            "custom_domain": "app.novarevenda.com",
            "primary_color": "#FF5500",
            "max_cameras": 300
        })
        assert response.status_code == 201

    def test_reseller_admin_cannot_access_master(self, reseller_admin_client):
        response = reseller_admin_client.get("/master/api/resellers/")
        assert response.status_code == 403

    def test_camera_limit_respected_across_tenants(self, db, reseller_with_license_50):
        """Soma de câmeras de todos os tenants do revendedor não excede licença."""
        tenant_a = TenantFactory(reseller=reseller_with_license_50)
        tenant_b = TenantFactory(reseller=reseller_with_license_50)
        CameraFactory.create_batch(30, tenant=tenant_a)
        CameraFactory.create_batch(20, tenant=tenant_b)
        # 51ª câmera deve falhar
        with pytest.raises(LicenseLimitExceeded):
            CameraFactory(tenant=tenant_a)
```

---

## 10. Testes E2E (Cypress)

```javascript
// cypress/e2e/white_label.cy.js
describe('White Label', () => {
  it('tela de login exibe logo do revendedor', () => {
    cy.visit('https://saopaulo.cidadesegura.com.br/login')
    cy.get('[data-cy=reseller-logo]').should('be.visible')
    cy.get('[data-cy=reseller-logo]').should('have.attr', 'src').and('include', 'cidadesegura')
    cy.get('body').should('not.contain', 'GT-Vision')
  })
})

// cypress/e2e/camera_flow.cy.js
describe('Fluxo de Câmera', () => {
  beforeEach(() => cy.loginAsAdmin())

  it('adiciona câmera RTSP e aparece no mapa', () => {
    cy.visit('/gestao/cameras/nova')
    cy.get('[data-cy=camera-name]').type('Câmera Centro 01')
    cy.get('[data-cy=stream-protocol]').select('rtsp')
    cy.get('[data-cy=stream-url]').type('rtsp://192.168.1.100:554/stream')
    cy.get('[data-cy=retention-days]').select('15')
    cy.get('[data-cy=submit]').click()
    cy.visit('/dashboard')
    cy.get('[data-cy=map]').contains('Câmera Centro 01')
  })

  it('habilita IA e exibe status pendente', () => {
    cy.visit('/gestao/cameras')
    cy.get('[data-cy=camera-row]').first().click()
    cy.get('[data-cy=ia-toggle]').click()
    cy.get('[data-cy=ia-status]').should('contain', 'IA Pendente')
  })
})

// cypress/e2e/roi.cy.js
describe('ROI', () => {
  it('desenha ROI e ativa IA da câmera', () => {
    cy.loginAsAdmin()
    cy.visit('/zona-de-interesse')
    cy.get('[data-cy=camera-select]').select('Câmera Centro 01')
    cy.get('[data-cy=roi-canvas]').should('be.visible')
    // simula desenho de polígono
    cy.get('[data-cy=roi-canvas]').trigger('mousedown', 50, 50)
      .trigger('mousemove', 200, 50)
      .trigger('mousemove', 200, 200)
      .trigger('mousemove', 50, 200)
      .trigger('dblclick')
    cy.get('[data-cy=roi-name]').type('Entrada Principal')
    cy.get('[data-cy=save-roi]').click()
    cy.get('[data-cy=success-toast]').should('be.visible')
  })
})
```

---

## 11. Configuração de Fixtures Globais

```python
# conftest.py

import pytest
from factory_boy import ...

@pytest.fixture
def reseller(db):
    return ResellerFactory()

@pytest.fixture
def tenant(db, reseller):
    return TenantFactory(reseller=reseller)

@pytest.fixture
def user(db, tenant):
    return UserFactory(tenant=tenant, role="operator")

@pytest.fixture
def auth_operator_client(client, user):
    token = get_jwt_token(user)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    client.defaults["HTTP_HOST"] = f"{user.tenant.subdomain}.{user.tenant.reseller.custom_domain}"
    return client

@pytest.fixture
def auth_admin_client(client, tenant):
    admin = UserFactory(tenant=tenant, role="city_admin")
    token = get_jwt_token(admin)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client

@pytest.fixture
def super_admin_client(client):
    admin = UserFactory(role="super_admin", tenant=None)
    token = get_jwt_token(admin)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    client.defaults["HTTP_HOST"] = "master.gt-vision.internal"
    return client
```

---

## 12. Comandos para Execução

```bash
# Rodar todos os testes
pytest --cov=apps --cov-report=html

# Apenas testes de isolamento de tenant
pytest tests/test_tenant_isolation.py -v

# Apenas testes de white label
pytest tests/test_middleware_tenant.py tests/test_api_theme.py -v

# Workers FastAPI
cd backend-fastapi && pytest workers/ -v --asyncio-mode=auto

# Cobertura mínima exigida (falha abaixo de 80%)
pytest --cov=apps --cov-fail-under=80

# E2E Cypress
npx cypress run --spec "cypress/e2e/**/*.cy.js"
```
