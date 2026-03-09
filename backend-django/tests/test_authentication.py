import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.core.cache import cache
from tests.factories import UserFactory, TenantFactory


@pytest.mark.django_db
class TestAuthentication:
    
    def setup_method(self):
        self.client = APIClient()
        cache.clear()

    def test_login_valid_returns_tokens(self):
        """Login válido deve retornar access e refresh tokens"""
        tenant = TenantFactory()
        user = UserFactory(email='test@example.com', password='testpass123', tenant=tenant)
        
        response = self.client.post('/api/v1/auth/login/', {
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        
        assert response.status_code == 200
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_login_invalid_returns_401(self):
        """Login inválido deve retornar 401"""
        response = self.client.post('/api/v1/auth/login/', {
            'email': 'wrong@example.com',
            'password': 'wrongpass'
        })
        
        assert response.status_code == 401

    def test_account_locked_after_5_failures(self):
        """Conta deve ser bloqueada após 5 tentativas falhas"""
        tenant = TenantFactory()
        user = UserFactory(email='lock@example.com', password='correct', tenant=tenant)
        
        # 5 tentativas falhas
        for _ in range(5):
            self.client.post('/api/v1/auth/login/', {
                'email': 'lock@example.com',
                'password': 'wrong'
            })
        
        # 6ª tentativa deve retornar 423 (Locked)
        response = self.client.post('/api/v1/auth/login/', {
            'email': 'lock@example.com',
            'password': 'correct'
        })
        
        assert response.status_code == 423
        assert 'bloqueada' in response.data['detail'].lower()

    def test_user_from_different_tenant_cannot_login(self):
        """Usuário de tenant A não pode logar em tenant B"""
        tenant_a = TenantFactory(subdomain='tenanta')
        tenant_b = TenantFactory(subdomain='tenantb')
        user = UserFactory(email='user@example.com', password='pass123', tenant=tenant_a)
        
        # Simula request de tenant B
        response = self.client.post('/api/v1/auth/login/', {
            'email': 'user@example.com',
            'password': 'pass123'
        }, HTTP_HOST='tenantb.example.com')
        
        assert response.status_code == 401

    def test_logout_invalidates_refresh_token(self):
        """Logout deve invalidar refresh token no Redis"""
        tenant = TenantFactory()
        user = UserFactory(email='logout@example.com', password='pass123', tenant=tenant)
        
        # Login
        login_response = self.client.post('/api/v1/auth/login/', {
            'email': 'logout@example.com',
            'password': 'pass123'
        })
        refresh_token = login_response.data['refresh']
        
        # Logout
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {login_response.data["access"]}')
        logout_response = self.client.post('/api/v1/auth/logout/', {
            'refresh': refresh_token
        })
        
        assert logout_response.status_code == 200
        
        # Tentar usar refresh token deve falhar
        refresh_response = self.client.post('/api/v1/auth/refresh/', {
            'refresh': refresh_token
        })
        
        assert refresh_response.status_code == 401

    def test_expired_token_returns_401(self):
        """Token expirado deve retornar 401"""
        expired_token = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE2MDAwMDAwMDB9.invalid'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {expired_token}')
        response = self.client.get('/api/v1/auth/me/')
        
        assert response.status_code == 401
