"""Views para analytics — ROI, DwellEvent, FaceProfile, FaceDetectionEvent e ingest interno."""
import functools
import logging
from typing import Any

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.cameras.models import Camera
from apps.events.models import Event

from .handlers import dispatch_ingest
from .models import DwellEvent, FaceDetectionEvent, FaceProfile, RegionOfInterest
from .serializers import (
    DwellEventSerializer,
    FaceDetectionEventSerializer,
    FaceProfileSerializer,
    RegionOfInterestCreateSerializer,
    RegionOfInterestSerializer,
)

logger = logging.getLogger(__name__)


def _require_analytics_key(func):
    """Decorator: exige header Authorization: Analytics <key>."""
    @functools.wraps(func)
    def wrapper(request: Request, *args: Any, **kwargs: Any):
        header = request.headers.get("Authorization", "")
        key = header.removeprefix("Analytics ").strip()
        expected = getattr(settings, "ANALYTICS_SERVICE_API_KEY", "")
        if not expected or key != expected:
            return Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
        return func(request, *args, **kwargs)
    return wrapper


class RegionOfInterestViewSet(viewsets.ModelViewSet):
    """ViewSet para CRUD de ROIs."""

    queryset = RegionOfInterest.objects.none()

    def get_serializer_class(self):
        """Usa serializer de criação para write, completo para read."""
        if self.action in ("create", "update", "partial_update"):
            return RegionOfInterestCreateSerializer
        return RegionOfInterestSerializer

    def get_queryset(self):
        """Retorna ROIs do tenant, com filtro opcional por câmera."""
        qs = RegionOfInterest.objects.filter(tenant=self.request.user.tenant)
        camera_id = self.request.query_params.get("camera")
        if camera_id:
            qs = qs.filter(camera_id=camera_id)
        return qs

    def perform_create(self, serializer: RegionOfInterestCreateSerializer) -> None:
        """Injeta tenant automaticamente."""
        serializer.save(tenant=self.request.user.tenant)


class FaceProfileViewSet(viewsets.ModelViewSet):
    """CRUD de perfis faciais cadastrados.

    ⚠ LGPD: o tenant precisa ter ``facial_recognition_enabled=True`` para criar perfis.
    DELETE por CPF disponível em ``DELETE /analytics/face-profiles/by-cpf/?cpf=XXX``.
    """

    serializer_class = FaceProfileSerializer
    queryset = FaceProfile.objects.none()

    def get_queryset(self):
        """Retorna perfis do tenant, sem expor embedding."""
        return FaceProfile.objects.filter(tenant=self.request.user.tenant)

    def perform_create(self, serializer: FaceProfileSerializer) -> None:
        """Valida gate LGPD e injeta tenant."""
        tenant = self.request.user.tenant
        if not tenant.facial_recognition_enabled:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                "Reconhecimento facial não está habilitado para este tenant. "
                "Aceite o termo LGPD em PATCH /api/v1/analytics/face-recognition/consent/ primeiro."
            )
        serializer.save(tenant=tenant)

    @action(detail=False, methods=["delete"], url_path="by-cpf")
    def delete_by_cpf(self, request: Request) -> Response:
        """Direito ao esquecimento LGPD: remove todos os perfis de um CPF.

        Query param: ``?cpf=000.000.000-00``
        """
        cpf = request.query_params.get("cpf", "").strip()
        if not cpf:
            return Response({"detail": "Query param 'cpf' obrigatório."}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = FaceProfile.objects.filter(
            tenant=request.user.tenant, cpf=cpf
        ).delete()

        return Response({"deleted": deleted}, status=status.HTTP_200_OK)


class FaceDetectionEventViewSet(viewsets.ReadOnlyModelViewSet):
    """Histórico de eventos de reconhecimento facial (somente leitura)."""

    serializer_class = FaceDetectionEventSerializer
    queryset = FaceDetectionEvent.objects.none()

    def get_queryset(self):
        """Retorna eventos do tenant com filtros opcionais."""
        qs = FaceDetectionEvent.objects.filter(
            tenant=self.request.user.tenant
        ).select_related("camera", "face_profile", "roi")

        camera_id = self.request.query_params.get("camera")
        if camera_id:
            qs = qs.filter(camera_id=camera_id)

        is_unknown = self.request.query_params.get("is_unknown")
        if is_unknown is not None:
            qs = qs.filter(is_unknown=is_unknown.lower() == "true")

        date_from = self.request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        return qs


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def accept_facial_recognition_consent(request: Request) -> Response:
    """Aceita o termo LGPD e habilita reconhecimento facial para o tenant.

    Body: ``{"confirm": true}``
    Sem confirmação explícita, a operação é recusada.
    """
    if not request.data.get("confirm"):
        return Response(
            {"detail": "Envie confirm=true para aceitar o termo LGPD de reconhecimento facial."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tenant = request.user.tenant
    tenant.facial_recognition_enabled = True
    tenant.facial_recognition_consent_at = timezone.now()
    tenant.save(update_fields=["facial_recognition_enabled", "facial_recognition_consent_at"])

    return Response({
        "facial_recognition_enabled": True,
        "facial_recognition_consent_at": tenant.facial_recognition_consent_at,
    })


class DwellEventViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet somente leitura para DwellEvents."""

    serializer_class = DwellEventSerializer
    queryset = DwellEvent.objects.none()

    def get_queryset(self):
        """Retorna eventos do tenant com filtros opcionais."""
        qs = DwellEvent.objects.filter(
            tenant=self.request.user.tenant
        ).select_related("camera", "roi")

        camera_id = self.request.query_params.get("camera")
        if camera_id:
            qs = qs.filter(camera_id=camera_id)

        is_valid = self.request.query_params.get("is_valid")
        if is_valid is not None:
            qs = qs.filter(is_valid=is_valid.lower() == "true")

        date_from = self.request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(entered_at__date__gte=date_from)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(entered_at__date__lte=date_to)

        return qs


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """Retorna estatísticas agregadas para o dashboard."""
    tenant = request.user.tenant
    today = timezone.now().date()

    cameras = Camera.objects.filter(tenant=tenant)
    total_cameras = cameras.count()
    online_cameras = cameras.filter(is_online=True).count()

    events_today = Event.objects.filter(
        tenant=tenant,
        created_at__date=today,
    )
    total_events_today = events_today.count()

    events_by_type = (
        events_today.values("event_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    events_by_type_today = {row["event_type"]: row["count"] for row in events_by_type}

    dwell_today = DwellEvent.objects.filter(
        tenant=tenant,
        entered_at__date=today,
        is_valid=True,
    ).count()

    return Response({
        "total_cameras": total_cameras,
        "online_cameras": online_cameras,
        "offline_cameras": total_cameras - online_cameras,
        "total_events_today": total_events_today,
        "dwell_events_today": dwell_today,
        "total_clips": 0,
        "events_by_type_today": events_by_type_today,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_events_by_hour(request):
    """Retorna contagem de eventos por hora das últimas 24h."""
    tenant = request.user.tenant
    now = timezone.now()
    since = now - timezone.timedelta(hours=24)

    from django.db.models.functions import TruncHour
    rows = (
        Event.objects.filter(tenant=tenant, created_at__gte=since)
        .annotate(hour=TruncHour("created_at"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )

    # Preenche todas as 24h com zero
    hour_map: dict[str, int] = {}
    for i in range(24):
        h = (since + timezone.timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        hour_map[h.strftime("%Hh")] = 0

    for row in rows:
        key = row["hour"].strftime("%Hh")
        hour_map[key] = row["count"]

    return Response([{"hour": k, "events": v} for k, v in hour_map.items()])


# ── Endpoints internos (analytics_service → Django) ───────────────────────────

@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
@throttle_classes([])
@_require_analytics_key
def ingest_event(request: Request) -> Response:
    """Recebe evento analítico do analytics_service e roteia pelo nome do plugin.

    Autenticação: header ``Authorization: Analytics <ANALYTICS_SERVICE_API_KEY>``.

    Body::

        {
          "plugin":     "vehicle_dwell",
          "camera_id":  5,
          "tenant_id":  1,
          "event_type": "analytics.vehicle.dwell",
          "payload":    { ... campos específicos do plugin ... }
        }
    """
    plugin: str = request.data.get("plugin", "")
    camera_id: int | None = request.data.get("camera_id")
    tenant_id: int | None = request.data.get("tenant_id")
    payload: dict = request.data.get("payload", {})

    if not plugin or camera_id is None or tenant_id is None:
        return Response(
            {"detail": "Campos obrigatórios: plugin, camera_id, tenant_id, payload"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    dispatched = dispatch_ingest(plugin, int(camera_id), int(tenant_id), payload)
    if not dispatched:
        return Response(
            {"detail": f"Plugin desconhecido: {plugin}"},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return Response({"status": "accepted"}, status=status.HTTP_202_ACCEPTED)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
@_require_analytics_key
def internal_rois(request: Request) -> Response:
    """Retorna ROIs ativas de uma câmera para o analytics_service.

    Autenticação: header ``Authorization: Analytics <ANALYTICS_SERVICE_API_KEY>``.
    Query param: ``?camera=<camera_id>``
    """
    camera_id = request.query_params.get("camera")
    if not camera_id:
        return Response(
            {"detail": "Query param 'camera' obrigatório"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        camera_id_int = int(camera_id)
    except ValueError:
        return Response({"detail": "camera deve ser inteiro"}, status=status.HTTP_400_BAD_REQUEST)

    rois = RegionOfInterest.objects.filter(
        camera_id=camera_id_int,
        is_active=True,
    ).values("id", "name", "ia_type", "polygon_points", "config")

    return Response(list(rois))
