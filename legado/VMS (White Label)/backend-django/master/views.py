from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.resellers.models import Reseller
from apps.franchise.models import License
from apps.tenants.models import Tenant
from apps.cameras.models import Camera
from apps.detections.models import AIEvent
from .models import AuditLog
from .permissions import IsSuperAdmin
from .serializers import (
    ResellerSerializer, LicenseSerializer,
    TenantSerializer, AuditLogSerializer,
)


# ---------------------------------------------------------------------------
# ViewSets
# ---------------------------------------------------------------------------

class ResellerViewSet(viewsets.ModelViewSet):
    """CRUD de revendedores — somente super_admin"""
    queryset = Reseller.objects.all()
    serializer_class = ResellerSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('active'):
            qs = qs.filter(active=self.request.query_params['active'] == 'true')
        return qs


class LicenseViewSet(viewsets.ModelViewSet):
    """CRUD de licenças — somente super_admin"""
    queryset = License.objects.select_related('reseller').all()
    serializer_class = LicenseSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]


class TenantViewSet(viewsets.ModelViewSet):
    """CRUD de tenants (cidades) — somente super_admin"""
    queryset = Tenant.objects.select_related('reseller', 'license').all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @action(detail=True, methods=['patch'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        """PATCH /master/api/tenants/{id}/toggle-active/"""
        tenant = self.get_object()
        tenant.active = not tenant.active
        tenant.save(update_fields=['active'])
        return Response(TenantSerializer(tenant).data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Logs de auditoria (somente leitura) — somente super_admin"""
    queryset = AuditLog.objects.select_related('user', 'target_tenant').all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]


# ---------------------------------------------------------------------------
# Standalone views
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def metrics(request):
    """
    GET /master/api/metrics/
    Retorna métricas agregadas para o dashboard master.
    """
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    resellers_active = Reseller.objects.filter(active=True).count()
    total_tenants = Tenant.objects.count()

    # Câmeras ativas por tenant (top 20)
    cameras_by_tenant = (
        Camera.objects
        .values('tenant__name')
        .annotate(total=Count('id'))
        .order_by('-total')[:20]
    )

    # Eventos de IA por dia (últimos 30 dias)
    events_by_day = (
        AIEvent.objects
        .filter(detected_at__gte=thirty_days_ago)
        .annotate(day=TruncDate('detected_at'))
        .values('day')
        .annotate(total=Count('id'))
        .order_by('day')
    )

    return Response({
        'resellers_active': resellers_active,
        'total_tenants': total_tenants,
        'cameras_by_tenant': list(cameras_by_tenant),
        'events_by_day': [
            {'date': e['day'].isoformat(), 'count': e['total']}
            for e in events_by_day
        ],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def impersonate(request, tenant_id):
    """
    POST /master/api/impersonate/{tenant_id}/
    Gera token JWT com escopo do tenant alvo para suporte técnico.
    Token válido por 1 hora. Registra log de auditoria imutável.
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id, active=True)
    except Tenant.DoesNotExist:
        return Response(
            {'detail': 'Tenant não encontrado ou inativo.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Gera token com claims do super_admin mas tenant_id alvo
    refresh = RefreshToken.for_user(request.user)
    refresh['user_id'] = str(request.user.id)
    refresh['tenant_id'] = str(tenant.id)
    refresh['role'] = request.user.role
    refresh['reseller_id'] = str(tenant.reseller_id)
    refresh['impersonating'] = True

    # Reduz validade para 1 hora
    refresh.set_exp(lifetime=timedelta(hours=1))
    refresh.access_token.set_exp(lifetime=timedelta(hours=1))

    # Log de auditoria
    AuditLog.objects.create(
        user=request.user,
        action='impersonate',
        target_tenant=tenant,
        details={
            'tenant_name': tenant.name,
            'tenant_subdomain': tenant.subdomain,
        },
        ip_address=_get_client_ip(request),
    )

    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'tenant': TenantSerializer(tenant).data,
    })


def _get_client_ip(request):
    """Extrai IP do cliente considerando proxies"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
