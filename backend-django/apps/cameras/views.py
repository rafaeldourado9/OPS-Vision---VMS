from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from apps.authentication.permissions import RolePermission
from .models import Camera
from .serializers import CameraSerializer


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
        tenant = self.request.tenant
        
        # Verifica limite de câmeras
        from apps.franchise.models import License
        current_count = Camera.objects.filter(tenant_id=tenant_id).count()
        license = License.objects.filter(reseller__tenants__id=tenant_id, active=True).first()
        max_cameras = license.max_cameras if license else 10
        
        if current_count >= max_cameras:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Limite de câmeras atingido para esta licença')
        
        serializer.save(tenant_id=tenant_id)

    @action(detail=True, methods=['get'])
    def thumbnail(self, request, pk=None):
        """GET /api/v1/cameras/{id}/thumbnail/"""
        camera = self.get_object()
        
        # Busca thumbnail do Redis
        thumbnail_key = f'thumbnail:{camera.id}'
        thumbnail_url = cache.get(thumbnail_key)
        
        if thumbnail_url:
            return Response({'url': thumbnail_url})
        
        return Response({'url': None}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'], url_path='stream-url')
    def stream_url(self, request, pk=None):
        """GET /api/v1/cameras/{id}/stream-url/ - Retorna URL WebRTC WHEP"""
        camera = self.get_object()

        host = request.get_host().split(':')[0]
        whep_url = f'http://{host}:8889/live/{request.tenant_id}/{camera.id}/whep'

        return Response({
            'url': whep_url,
            'online': camera.online,
        })

    @action(detail=True, methods=['get'], url_path='hls-url')
    def hls_url(self, request, pk=None):
        """GET /api/v1/cameras/{id}/hls-url/ - Retorna URL HLS"""
        camera = self.get_object()

        host = request.get_host().split(':')[0]
        hls_url = f'http://{host}:8888/live/{request.tenant_id}/{camera.id}/index.m3u8'

        return Response({
            'url': hls_url,
            'online': camera.online,
        })

    @action(detail=True, methods=['get'])
    def segments(self, request, pk=None):
        """GET /api/v1/cameras/{id}/segments/ - Lista segmentos disponíveis"""
        camera = self.get_object()
        
        from apps.segments.models import Segment
        from apps.segments.serializers import SegmentSerializer
        
        segments = Segment.objects.filter(camera=camera).order_by('start_time')
        serializer = SegmentSerializer(segments, many=True)
        
        return Response(serializer.data)
