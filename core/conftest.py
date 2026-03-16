"""Fixtures globais para todos os testes Django."""
import pytest

from tests.factories import TenantFactory, UserFactory


@pytest.fixture(autouse=True)
def clear_cache():
    """Limpa o cache antes de cada teste para evitar colisões de dedup."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def tenant(db):
    """Cria um tenant para testes."""
    return TenantFactory()


@pytest.fixture
def user(db, tenant):
    """Cria um usuário autenticado para testes."""
    return UserFactory(tenant=tenant)


@pytest.fixture
def api_client():
    """Retorna um APIClient do DRF."""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def authenticated_client(api_client, user):
    """Retorna um APIClient autenticado."""
    api_client.force_authenticate(user=user)
    return api_client
