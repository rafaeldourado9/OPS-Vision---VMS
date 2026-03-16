"""Abstração Redis para cache do VMS."""

from django.core.cache import cache


def get_camera_status(camera_id: int) -> bool | None:
    """Retorna o status online/offline da câmera no cache.

    Args:
        camera_id: ID da câmera.

    Returns:
        True/False se encontrado no cache, None se expirado.
    """
    return cache.get(f"camera:{camera_id}:online")


def set_camera_status(camera_id: int, is_online: bool, ttl: int = 30) -> None:
    """Armazena status da câmera no cache.

    Args:
        camera_id: ID da câmera.
        is_online: Se a câmera está online.
        ttl: Tempo de vida em segundos (padrão 30s).
    """
    cache.set(f"camera:{camera_id}:online", is_online, timeout=ttl)


def invalidate_camera_status(camera_id: int) -> None:
    """Remove status da câmera do cache.

    Args:
        camera_id: ID da câmera.
    """
    cache.delete(f"camera:{camera_id}:online")
