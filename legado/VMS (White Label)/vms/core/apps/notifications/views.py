"""Views para o app de notificações."""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import NotificationLog, NotificationRule
from .serializers import NotificationLogSerializer, NotificationRuleSerializer


class NotificationRuleViewSet(viewsets.ModelViewSet):
    """API para CRUD de regras de notificação.

    Filtra as regras pelo tenant do request.user.
    """

    serializer_class = NotificationRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Retorna apenas as regras do tenant do usuário."""
        if not hasattr(self.request.user, "tenant"):
            return NotificationRule.objects.none()
        return NotificationRule.objects.filter(tenant=self.request.user.tenant)


class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """API para leitura de logs de notificação.

    Filtra os logs para exibir apenas aqueles cujas regras pertencem
    ao tenant do request.user.
    """

    serializer_class = NotificationLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Retorna apenas logs de regras do tenant do usuário."""
        if not hasattr(self.request.user, "tenant"):
            return NotificationLog.objects.none()
        return NotificationLog.objects.filter(
            rule__tenant=self.request.user.tenant
        ).order_by("-created_at")
