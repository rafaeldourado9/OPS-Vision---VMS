"""Lógica de domínio para users e tenants."""
from django.contrib.auth import get_user_model

from .models import Tenant

User = get_user_model()


def create_tenant(name: str, slug: str) -> Tenant:
    """Cria um novo tenant.

    Args:
        name: Nome do tenant.
        slug: Slug único do tenant.

    Returns:
        Tenant criado.
    """
    return Tenant.objects.create(name=name, slug=slug)


def create_user(
    username: str,
    email: str,
    password: str,
    tenant_id: int,
    is_staff: bool = False,
) -> "User":
    """Cria um novo usuário vinculado a um tenant.

    Args:
        username: Nome de usuário.
        email: Email do usuário.
        password: Senha (será hasheada).
        tenant_id: ID do tenant.
        is_staff: Se é staff/admin.

    Returns:
        User criado.
    """
    return User.objects.create_user(
        username=username,
        email=email,
        password=password,
        tenant_id=tenant_id,
        is_staff=is_staff,
    )
