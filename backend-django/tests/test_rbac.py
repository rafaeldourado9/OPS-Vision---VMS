import pytest
from rest_framework.test import APIClient
from rest_framework.exceptions import PermissionDenied
from apps.authentication.permissions import require_role, RolePermission
from tests.factories import UserFactory, TenantFactory


@pytest.mark.django_db
class TestRBAC:
    
    def setup_method(self):
        self.client = APIClient()
        self.tenant = TenantFactory()

    def test_require_role_decorator_allows_authorized_role(self):
        """Decorator deve permitir acesso para role autorizado"""
        user = UserFactory(role='city_admin', tenant=self.tenant)
        
        @require_role('city_admin', 'supervisor')
        def protected_view(request):
            return {'success': True}
        
        class MockRequest:
            user = user
        
        result = protected_view(MockRequest())
        assert result['success'] is True

    def test_require_role_decorator_denies_unauthorized_role(self):
        """Decorator deve negar acesso para role não autorizado"""
        user = UserFactory(role='operator', tenant=self.tenant)
        
        @require_role('city_admin', 'supervisor')
        def protected_view(request):
            return {'success': True}
        
        class MockRequest:
            user = user
        
        with pytest.raises(PermissionDenied) as exc:
            protected_view(MockRequest())
        
        assert 'city_admin' in str(exc.value)

    def test_role_permission_class_allows_authorized(self):
        """RolePermission deve permitir acesso para role autorizado"""
        user = UserFactory(role='supervisor', tenant=self.tenant)
        
        class TestPermission(RolePermission):
            allowed_roles = ['supervisor', 'city_admin']
        
        permission = TestPermission()
        
        class MockRequest:
            pass
        
        request = MockRequest()
        request.user = user
        
        assert permission.has_permission(request, None) is True

    def test_role_permission_class_denies_unauthorized(self):
        """RolePermission deve negar acesso para role não autorizado"""
        user = UserFactory(role='operator', tenant=self.tenant)
        
        class TestPermission(RolePermission):
            allowed_roles = ['supervisor', 'city_admin']
        
        permission = TestPermission()
        
        class MockRequest:
            pass
        
        request = MockRequest()
        request.user = user
        
        assert permission.has_permission(request, None) is False
