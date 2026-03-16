"""Views para a API de Eventos."""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets
from rest_framework.pagination import PageNumberPagination

from .filters import EventFilter
from .models import Event
from .serializers import EventSerializer


class EventPagination(PageNumberPagination):
    """Paginação padrão para Eventos, com limite rígido."""
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint que permite visualizar Eventos.
    
    Suporta paginação e filtragem por tenant, câmera, tipo de evento,
    data de criação e detalhes de placa/confiança (ALPR).
    """
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = EventPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = EventFilter

    def get_queryset(self):
        """Retorna apenas eventos do tenant do usuário autenticado."""
        return Event.objects.filter(
            tenant_id=self.request.user.tenant_id
        ).select_related("camera").order_by("-created_at")
