import pytest
from rest_framework.test import APIClient
from django.utils import timezone
from datetime import date, timedelta

from tests.factories import (
    ResellerFactory, TenantFactory,
    LicenseFactory, UserFactory,
)
from master.models import AuditLog


@pytest.mark.django_db
class TestMasterPanel:
    """Testes para o painel master de franquia"""

    def setup_method(self):
        self.client = APIClient()
        self.super_admin = UserFactory(
            role='super_admin',
            tenant=None,
            password='admin123',
        )
        self.reseller_admin = UserFactory(
            role='reseller_admin',
            password='reseller123',
        )

    # ---- Acesso ----

    def test_super_admin_can_create_reseller(self):
        """Super admin consegue criar revendedor"""
        self.client.force_authenticate(user=self.super_admin)

        response = self.client.post('/master/api/resellers/', {
            'name': 'Novo Revendedor',
            'slug': 'novo-revendedor',
            'primary_color': '#FF5500',
            'secondary_color': '#0055FF',
        })

        assert response.status_code == 201
        assert response.data['name'] == 'Novo Revendedor'
        assert response.data['slug'] == 'novo-revendedor'

    def test_reseller_admin_cannot_access_master(self):
        """Reseller admin não tem acesso ao painel master"""
        self.client.force_authenticate(user=self.reseller_admin)

        response = self.client.get('/master/api/resellers/')

        assert response.status_code == 403

    def test_unauthenticated_cannot_access_master(self):
        """Usuário não autenticado não tem acesso"""
        response = self.client.get('/master/api/resellers/')

        assert response.status_code in (401, 403)

    # ---- CRUD ----

    def test_list_resellers(self):
        """Listagem de revendedores retorna dados"""
        self.client.force_authenticate(user=self.super_admin)
        ResellerFactory()
        ResellerFactory()

        response = self.client.get('/master/api/resellers/')

        assert response.status_code == 200
        assert len(response.data) >= 2

    def test_create_license(self):
        """Criar licença para revendedor"""
        self.client.force_authenticate(user=self.super_admin)
        reseller = ResellerFactory()

        response = self.client.post('/master/api/licenses/', {
            'reseller': str(reseller.id),
            'max_cameras': 50,
            'valid_until': (date.today() + timedelta(days=365)).isoformat(),
        })

        assert response.status_code == 201
        assert response.data['max_cameras'] == 50

    def test_create_tenant(self):
        """Criar tenant (cidade)"""
        self.client.force_authenticate(user=self.super_admin)
        reseller = ResellerFactory()
        license = LicenseFactory(reseller=reseller)

        response = self.client.post('/master/api/tenants/', {
            'reseller': str(reseller.id),
            'license': str(license.id),
            'name': 'Cidade Nova',
            'subdomain': 'cidadenova',
        })

        assert response.status_code == 201
        assert response.data['name'] == 'Cidade Nova'

    def test_toggle_tenant_active(self):
        """Ativar/desativar tenant"""
        self.client.force_authenticate(user=self.super_admin)
        tenant = TenantFactory(active=True)

        response = self.client.patch(f'/master/api/tenants/{tenant.id}/toggle-active/')

        assert response.status_code == 200
        assert response.data['active'] is False

    # ---- Impersonação ----

    def test_impersonation_generates_audit_log(self):
        """Impersonação gera log de auditoria"""
        self.client.force_authenticate(user=self.super_admin)
        tenant = TenantFactory()

        response = self.client.post(f'/master/api/impersonate/{tenant.id}/')

        assert response.status_code == 200
        assert 'access' in response.data
        assert 'refresh' in response.data

        # Verifica log de auditoria
        log = AuditLog.objects.filter(
            user=self.super_admin,
            action='impersonate',
            target_tenant=tenant,
        ).first()

        assert log is not None
        assert log.details['tenant_name'] == tenant.name

    def test_impersonation_denied_for_non_super_admin(self):
        """Impersonação negada para não super_admin"""
        self.client.force_authenticate(user=self.reseller_admin)
        tenant = TenantFactory()

        response = self.client.post(f'/master/api/impersonate/{tenant.id}/')

        assert response.status_code == 403

    # ---- Métricas ----

    def test_metrics_returns_correct_data(self):
        """Métricas retornam dados corretos"""
        self.client.force_authenticate(user=self.super_admin)
        ResellerFactory(active=True)
        TenantFactory()

        response = self.client.get('/master/api/metrics/')

        assert response.status_code == 200
        assert 'resellers_active' in response.data
        assert 'total_tenants' in response.data
        assert 'cameras_by_tenant' in response.data
        assert 'events_by_day' in response.data
        assert response.data['resellers_active'] >= 1
