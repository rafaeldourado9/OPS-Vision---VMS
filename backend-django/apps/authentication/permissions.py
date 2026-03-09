from functools import wraps
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


def require_role(*allowed_roles):
    """Decorator para verificar roles do usuário"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, 'user') or not request.user.is_authenticated:
                raise PermissionDenied('Autenticação necessária.')
            
            if request.user.role not in allowed_roles:
                raise PermissionDenied(
                    f'Acesso negado. Roles permitidos: {", ".join(allowed_roles)}'
                )
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class RolePermission(BasePermission):
    """Permission class para DRF ViewSets"""
    allowed_roles = []

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if not self.allowed_roles:
            return True
        
        return request.user.role in self.allowed_roles
