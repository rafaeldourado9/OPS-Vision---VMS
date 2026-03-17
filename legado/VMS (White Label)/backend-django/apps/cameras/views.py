import base64
import logging
import os
import subprocess
import tempfile
import threading

import redis as _redis
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from apps.authentication.permissions import RolePermission
from .models import Camera, DetectionMask
from .serializers import CameraSerializer, DetectionMaskSerializer

logger = logging.getLogger(__name__)

MEDIAMTX_HLS_INTERNAL = os.getenv('MEDIAMTX_HLS_INTERNAL', 'http://mediamtx:8888')
THUMBNAIL_CACHE_TTL = 300  # 5 minutos
THUMBNAIL_QUALITY = 5  # FFmpeg JPEG quality (2=best, 31=worst)

_redis_client = None


def _get_redis():
    """Client Redis direto (sem pickle do Django cache framework)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = _redis.from_url(
            settings.CACHES['default']['LOCATION'],
            decode_responses=True,
        )
    return _redis_client


def generate_thumbnail_bytes(hls_url: str) -> bytes | None:
    """Captura um frame do stream HLS usando FFmpeg e retorna os bytes JPEG."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name

        result = subprocess.run(
            [
                'ffmpeg', '-y',
                '-i', hls_url,
                '-vframes', '1',
                '-q:v', str(THUMBNAIL_QUALITY),
                '-vf', 'scale=640:-1',
                tmp_path,
            ],
            capture_output=True,
            timeout=15,
        )

        if result.returncode == 0 and os.path.getsize(tmp_path) > 0:
            with open(tmp_path, 'rb') as f:
                return f.read()
        logger.warning('FFmpeg failed for %s: %s', hls_url, result.stderr[:200])
    except subprocess.TimeoutExpired:
        logger.warning('FFmpeg timeout for %s', hls_url)
    except Exception as exc:
        logger.warning('Thumbnail generation error: %s', exc)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    return None


def _schedule_thumbnail_generation(camera_id: str, tenant_id: str, delay: int = 10, retries: int = 3):
    """Gera thumbnail em background com retry."""
    def _worker():
        import time
        for attempt in range(retries):
            time.sleep(delay * (attempt + 1))
            hls_url = f'{MEDIAMTX_HLS_INTERNAL}/live/{tenant_id}/{camera_id}/index.m3u8'
            image_bytes = generate_thumbnail_bytes(hls_url)
            if image_bytes:
                r = _get_redis()
                r.setex(
                    f'thumbnail:{camera_id}',
                    THUMBNAIL_CACHE_TTL,
                    base64.b64encode(image_bytes).decode(),
                )
                logger.info('Thumbnail generated for camera %s (attempt %d)', camera_id, attempt + 1)
                return
            logger.info('Thumbnail attempt %d/%d failed for camera %s', attempt + 1, retries, camera_id)
    threading.Thread(target=_worker, daemon=True).start()


class CityAdminPermission(RolePermission):
    allowed_roles = ['city_admin', 'reseller_admin', 'super_admin']


class CameraViewSet(viewsets.ModelViewSet):
    serializer_class = CameraSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtra câmeras por tenant automaticamente"""
        tenant_id = getattr(self.request, 'tenant_id', None)
        if tenant_id:
            return Camera.objects.filter(tenant_id=tenant_id)
        return Camera.objects.none()

    def get_permissions(self):
        """Apenas city_admin pode criar/editar/deletar"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), CityAdminPermission()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        """Valida limite de licença antes de criar"""
        tenant_id = self.request.tenant_id

        from apps.franchise.models import License
        current_count = Camera.objects.filter(tenant_id=tenant_id).count()
        license_obj = License.objects.filter(reseller__tenants__id=tenant_id, active=True).first()
        max_cameras = license_obj.max_cameras if license_obj else 10

        if current_count >= max_cameras:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Limite de câmeras atingido para esta licença')

        camera = serializer.save(tenant_id=tenant_id)
        _schedule_thumbnail_generation(str(camera.id), str(tenant_id))

    @action(detail=True, methods=['get'])
    def thumbnail(self, request, pk=None):
        """GET /api/v1/cameras/{id}/thumbnail/ — retorna imagem JPEG."""
        camera = self.get_object()
        thumbnail_key = f'thumbnail:{camera.id}'

        r = _get_redis()
        cached_b64 = r.get(thumbnail_key)
        if cached_b64:
            return HttpResponse(
                base64.b64decode(cached_b64),
                content_type='image/jpeg',
                headers={'Cache-Control': 'public, max-age=60'},
            )

        tenant_id = getattr(request, 'tenant_id', None)
        hls_url = f'{MEDIAMTX_HLS_INTERNAL}/live/{tenant_id}/{camera.id}/index.m3u8'
        image_bytes = generate_thumbnail_bytes(hls_url)

        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode()
            r.setex(thumbnail_key, THUMBNAIL_CACHE_TTL, b64)
            return HttpResponse(
                image_bytes,
                content_type='image/jpeg',
                headers={'Cache-Control': 'public, max-age=60'},
            )

        return HttpResponse(status=404)

    @action(detail=True, methods=['get'])
    def snapshot(self, request, pk=None):
        """GET /api/v1/cameras/{id}/snapshot/ — alias de thumbnail para o editor de ROI."""
        return self.thumbnail(request, pk=pk)

    @action(detail=True, methods=['get'], url_path='stream-url')
    def stream_url(self, request, pk=None):
        """GET /api/v1/cameras/{id}/stream-url/ - Retorna URL WebRTC WHEP"""
        camera = self.get_object()

        host = request.get_host().split(':')[0]
        whep_url = f'http://{host}/webrtc/live/{request.tenant_id}/{camera.id}/whep'

        host = request.get_host().split(':')[0]
        hls_url = f'http://{host}/hls/live/{request.tenant_id}/{camera.id}/index.m3u8'

        return Response({
            'url': whep_url,
            'webrtc_whep': whep_url,
            'hls': hls_url,
            'online': camera.online,
        })

    @action(detail=True, methods=['get'], url_path='hls-url')
    def hls_url(self, request, pk=None):
        """GET /api/v1/cameras/{id}/hls-url/ - Retorna URL HLS"""
        camera = self.get_object()

        host = request.get_host().split(':')[0]
        hls_url = f'http://{host}/hls/live/{request.tenant_id}/{camera.id}/index.m3u8'

        return Response({
            'url': hls_url,
            'online': camera.online,
        })

    @action(detail=True, methods=['get'])
    def heatmap(self, request, pk=None):
        """GET /api/v1/cameras/{id}/heatmap/ — retorna imagem JPEG do mapa de calor."""
        camera = self.get_object()
        storage_path = os.getenv('MEDIA_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'storage', 'media'))
        # Heatmaps are stored at /app/storage/heatmaps/ (not inside media root)
        base_storage = os.getenv('STORAGE_PATH', '/app/storage')
        heatmap_path = os.path.join(base_storage, 'heatmaps', f'{camera.id}.jpg')

        if os.path.exists(heatmap_path):
            with open(heatmap_path, 'rb') as f:
                return HttpResponse(
                    f.read(),
                    content_type='image/jpeg',
                    headers={'Cache-Control': 'no-cache'},
                )
        return HttpResponse(status=404)

    @action(detail=True, methods=['get'])
    def segments(self, request, pk=None):
        """GET /api/v1/cameras/{id}/segments/ - Lista segmentos disponíveis"""
        camera = self.get_object()

        from apps.segments.models import Segment
        from apps.segments.serializers import SegmentSerializer

        segments = Segment.objects.filter(camera=camera).order_by('start_time')
        serializer = SegmentSerializer(segments, many=True)

        return Response(serializer.data)


class DetectionMaskViewSet(viewsets.ModelViewSet):
    """CRUD de máscaras de detecção."""
    serializer_class = DetectionMaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant_id = getattr(self.request, 'tenant_id', None)
        qs = DetectionMask.objects.filter(tenant_id=tenant_id)
        camera_id = self.request.query_params.get('camera_id')
        if camera_id:
            qs = qs.filter(camera_id=camera_id)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), CityAdminPermission()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        tenant_id = self.request.tenant_id
        serializer.save(tenant_id=tenant_id)
