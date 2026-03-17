import pytest
import json
from unittest.mock import Mock, patch
from django.test import RequestFactory
from django.core.cache import cache
from middleware.tenant import TenantMiddleware
from tests.factories import ResellerFactory, TenantFactory


@pytest.mark.django_db
class TestTenantMiddleware:
    
    def setup_method(self):
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(get_response=lambda r: Mock())
        cache.clear()

    def test_resolve_tenant_by_custom_domain(self):
        """Deve resolver tenant por custom_domain"""
        reseller = ResellerFactory(custom_domain='custom.example.com')
        tenant = TenantFactory(reseller=reseller)
        
        request = self.factory.get('/')
        request.META['HTTP_HOST'] = 'custom.example.com'
        
        self.middleware(request)
        
        assert hasattr(request, 'tenant')
        assert hasattr(request, 'reseller')
        assert request.reseller.id == str(reseller.id)

    def test_resolve_tenant_by_subdomain(self):
        """Deve resolver tenant por subdomain"""
        tenant = TenantFactory(subdomain='city1')
        
        request = self.factory.get('/')
        request.META['HTTP_HOST'] = 'city1.gtvision.com'
        
        self.middleware(request)
        
        assert hasattr(request, 'tenant')
        assert request.tenant.subdomain == 'city1'

    def test_cache_hit(self):
        """Deve usar cache quando disponível"""
        cache_data = {
            'tenant_id': 'test-tenant-id',
            'reseller_id': 'test-reseller-id',
            'tenant': {'id': 'test-tenant-id', 'name': 'Test', 'subdomain': 'test'},
            'reseller': {
                'id': 'test-reseller-id',
                'name': 'Test Reseller',
                'slug': 'test',
                'primary_color': '#000',
                'secondary_color': '#fff',
                'logo_url': None,
                'favicon_url': None,
            }
        }
        cache.set('wl:cached.example.com', json.dumps(cache_data), 300)
        
        request = self.factory.get('/')
        request.META['HTTP_HOST'] = 'cached.example.com'
        
        with patch('middleware.tenant.Reseller.objects.filter') as mock_filter:
            self.middleware(request)
            mock_filter.assert_not_called()  # Não deve consultar o banco
        
        assert request.tenant_id == 'test-tenant-id'

    def test_unknown_host_returns_404(self):
        """Deve retornar 404 para host desconhecido"""
        request = self.factory.get('/')
        request.META['HTTP_HOST'] = 'unknown.example.com'
        
        response = self.middleware(request)
        
        assert response.status_code == 404

    def test_inactive_tenant_returns_404(self):
        """Deve retornar 404 para tenant inativo"""
        tenant = TenantFactory(subdomain='inactive', active=False)
        
        request = self.factory.get('/')
        request.META['HTTP_HOST'] = 'inactive.gtvision.com'
        
        response = self.middleware(request)
        
        assert response.status_code == 404

    def test_cache_ttl_5_minutes(self):
        """Cache deve ter TTL de 5 minutos (300 segundos)"""
        tenant = TenantFactory(subdomain='ttltest')
        
        request = self.factory.get('/')
        request.META['HTTP_HOST'] = 'ttltest.gtvision.com'
        
        self.middleware(request)
        
        cache_key = 'wl:ttltest.gtvision.com'
        ttl = cache.ttl(cache_key)
        
        assert ttl > 0
        assert ttl <= 300
