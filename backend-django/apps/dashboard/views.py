import os
from pathlib import Path

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Count, Sum
from django.db.models.functions import ExtractHour, TruncDate, TruncHour
from django.http import FileResponse, Http404
from datetime import timedelta

from apps.cameras.models import Camera
from apps.detections.models import AIEvent
from apps.segments.models import Clip

STORAGE_PATH = os.getenv('STORAGE_PATH', '/app/storage')


# ---------------------------------------------------------------------------
# Dashboard principal
# ---------------------------------------------------------------------------

class DashboardStatsView(APIView):
    """GET /api/v1/dashboard/stats/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant_id = getattr(request, 'tenant_id', None)
        today = timezone.now().date()

        cameras = Camera.objects.filter(tenant_id=tenant_id)
        total_cameras  = cameras.count()
        online_cameras = cameras.filter(online=True).count()

        total_detections_today = AIEvent.objects.filter(
            tenant_id=tenant_id, detected_at__date=today,
        ).count()

        total_clips = Clip.objects.filter(camera__tenant_id=tenant_id).count()

        # Contagem por tipo de evento hoje
        events_by_type = (
            AIEvent.objects
            .filter(tenant_id=tenant_id, detected_at__date=today)
            .values('event_type')
            .annotate(count=Count('id'))
        )
        events_map = {e['event_type']: e['count'] for e in events_by_type}

        return Response({
            'total_cameras':          total_cameras,
            'online_cameras':         online_cameras,
            'offline_cameras':        total_cameras - online_cameras,
            'total_detections_today': total_detections_today,
            'total_clips':            total_clips,
            'storage_used_gb':        0,
            'events_by_type_today':   events_map,
        })


class DashboardDetectionsByHourView(APIView):
    """GET /api/v1/dashboard/detections-by-hour/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant_id = getattr(request, 'tenant_id', None)
        since = timezone.now() - timedelta(hours=24)

        counts = (
            AIEvent.objects
            .filter(tenant_id=tenant_id, detected_at__gte=since)
            .annotate(hour=ExtractHour('detected_at'))
            .values('hour')
            .annotate(detections=Count('id'))
            .order_by('hour')
        )

        counts_map = {item['hour']: item['detections'] for item in counts}
        data = [
            {'hour': f'{h:02d}', 'detections': counts_map.get(h, 0)}
            for h in range(24)
        ]
        return Response(data)


# ---------------------------------------------------------------------------
# Analytics de tráfego
# ---------------------------------------------------------------------------

class TrafficByHourView(APIView):
    """
    GET /api/v1/analytics/traffic-by-hour/
    Query params: event_type (vehicle_traffic|human_traffic), camera_id, hours (default 24)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant_id  = getattr(request, 'tenant_id', None)
        event_type = request.query_params.get('event_type', 'human_traffic')
        camera_id  = request.query_params.get('camera_id')
        hours      = int(request.query_params.get('hours', 24))

        since = timezone.now() - timedelta(hours=hours)

        qs = AIEvent.objects.filter(
            tenant_id=tenant_id,
            event_type=event_type,
            detected_at__gte=since,
        )
        if camera_id:
            qs = qs.filter(camera_id=camera_id)

        counts = (
            qs.annotate(hour=ExtractHour('detected_at'))
            .values('hour')
            .annotate(events=Count('id'))
            .order_by('hour')
        )

        counts_map = {item['hour']: item['events'] for item in counts}
        data = [
            {'hour': f'{h:02d}:00', 'events': counts_map.get(h, 0)}
            for h in range(hours if hours <= 24 else 24)
        ]
        return Response({'event_type': event_type, 'data': data})


class TrafficByDayView(APIView):
    """
    GET /api/v1/analytics/traffic-by-day/
    Query params: event_type, camera_id, days (default 7)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant_id  = getattr(request, 'tenant_id', None)
        event_type = request.query_params.get('event_type', 'human_traffic')
        camera_id  = request.query_params.get('camera_id')
        days       = int(request.query_params.get('days', 7))

        since = timezone.now() - timedelta(days=days)

        qs = AIEvent.objects.filter(
            tenant_id=tenant_id,
            event_type=event_type,
            detected_at__gte=since,
        )
        if camera_id:
            qs = qs.filter(camera_id=camera_id)

        counts = (
            qs.annotate(day=TruncDate('detected_at'))
            .values('day')
            .annotate(events=Count('id'))
            .order_by('day')
        )

        return Response({
            'event_type': event_type,
            'data': [
                {'day': item['day'].isoformat(), 'events': item['events']}
                for item in counts
            ],
        })


class EventsByTypeView(APIView):
    """
    GET /api/v1/analytics/events-by-type/
    Query params: camera_id, days (default 7)
    Retorna contagem de eventos agrupados por tipo no período.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant_id = getattr(request, 'tenant_id', None)
        camera_id = request.query_params.get('camera_id')
        days      = int(request.query_params.get('days', 7))

        since = timezone.now() - timedelta(days=days)

        qs = AIEvent.objects.filter(tenant_id=tenant_id, detected_at__gte=since)
        if camera_id:
            qs = qs.filter(camera_id=camera_id)

        counts = (
            qs.values('event_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        return Response({
            'period_days': days,
            'data': list(counts),
        })


class QueueStatsView(APIView):
    """
    GET /api/v1/analytics/queue-stats/
    Query params: camera_id, hours (default 24)
    Retorna últimos alertas de fila com count e avg_wait.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant_id = getattr(request, 'tenant_id', None)
        camera_id = request.query_params.get('camera_id')
        hours     = int(request.query_params.get('hours', 24))

        since = timezone.now() - timedelta(hours=hours)

        qs = AIEvent.objects.filter(
            tenant_id=tenant_id,
            event_type='queue_alert',
            detected_at__gte=since,
        ).select_related('camera')

        if camera_id:
            qs = qs.filter(camera_id=camera_id)

        data = [
            {
                'camera':           evt.camera.name,
                'camera_id':        str(evt.camera_id),
                'count':            evt.event_data.get('count', 0),
                'avg_wait_seconds': evt.event_data.get('avg_wait_seconds', 0),
                'max_wait_seconds': evt.event_data.get('max_wait_seconds', 0),
                'detected_at':      evt.detected_at.isoformat(),
            }
            for evt in qs.order_by('-detected_at')[:100]
        ]

        return Response({'period_hours': hours, 'data': data})


# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------

class CameraHeatmapView(APIView):
    """
    GET /api/v1/cameras/{camera_id}/heatmap/
    Retorna a imagem JPEG do mapa de calor gerado pelo AI worker.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, camera_id):
        tenant_id = getattr(request, 'tenant_id', None)

        # Verifica que a câmera pertence ao tenant
        if not Camera.objects.filter(id=camera_id, tenant_id=tenant_id).exists():
            raise Http404

        heatmap_path = Path(STORAGE_PATH) / 'heatmaps' / f'{camera_id}.jpg'

        if not heatmap_path.exists():
            return Response({'detail': 'Mapa de calor ainda não disponível.'}, status=404)

        return FileResponse(open(heatmap_path, 'rb'), content_type='image/jpeg')


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

class SystemInfoView(APIView):
    """GET /api/v1/system/info/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db import connection
        from django.core.cache import cache

        db_ok = True
        try:
            connection.ensure_connection()
        except Exception:
            db_ok = False

        redis_ok = True
        try:
            cache.set('healthcheck', '1', 5)
            redis_ok = cache.get('healthcheck') == '1'
        except Exception:
            redis_ok = False

        return Response({
            'version': '1.0.0',
            'environment': 'production',
            'services': {
                'database': 'online' if db_ok else 'offline',
                'redis':    'online' if redis_ok else 'offline',
            },
        })
