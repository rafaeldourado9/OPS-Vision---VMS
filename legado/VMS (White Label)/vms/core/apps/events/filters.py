"""Filtros para a API de Eventos."""
import django_filters

from .models import Event


class EventFilter(django_filters.FilterSet):
    """FilterSet para consultas avançadas de Eventos."""

    created_from = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_to = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    confidence_gte = django_filters.NumberFilter(field_name="confidence", lookup_expr="gte")
    confidence_lte = django_filters.NumberFilter(field_name="confidence", lookup_expr="lte")

    plate__icontains = django_filters.CharFilter(field_name="plate", lookup_expr="icontains")

    class Meta:
        model = Event
        fields = ["camera_id", "event_type", "plate"]
