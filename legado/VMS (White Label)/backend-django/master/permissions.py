from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    """Permite acesso apenas para super_admin"""
    message = 'Acesso restrito a super administradores.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'super_admin'
        )
