import json
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from django.db import transaction
from apps.authentication.permissions import RolePermission
from apps.cameras.models import Camera
from .models import RegionOfInterest
from .serializers import RegionOfInterestSerializer


class CityAdminPermission(RolePermission):
    allowed_roles = ['city_admin', 'reseller_admin', 'super_admin']


class RegionOfInterestViewSet(viewsets.ModelViewSet):
    serializer_class = RegionOfInterestSerializer
    permission_classes = [IsAuthenticated, CityAdminPermission]

    def get_queryset(self):
        """Filtra ROIs por tenant e opcionalmente por camera_id"""
        tenant_id = getattr(self.request, 'tenant_id', None)
        queryset = RegionOfInterest.objects.filter(tenant_id=tenant_id)
        
        camera_id = self.request.query_params.get('camera_id')
        if camera_id:
            queryset = queryset.filter(camera_id=camera_id)
        
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        """Cria ROI e atualiza status da câmera para active"""
        tenant_id = self.request.tenant_id
        roi = serializer.save(tenant_id=tenant_id)
        
        # Atualiza câmera para active
        camera = roi.camera
        if camera.ia_status == 'ia_pending':
            camera.ia_status = 'active'
            camera.save()
        
        # Publica mensagem RabbitMQ roi.updated
        self.publish_roi_updated(camera)

    @transaction.atomic
    def perform_destroy(self, instance):
        """Deleta ROI e verifica se deve mudar câmera para ia_pending"""
        camera = instance.camera
        instance.delete()
        
        # Se não há mais ROIs, volta para ia_pending
        remaining_rois = RegionOfInterest.objects.filter(camera=camera, active=True).count()
        if remaining_rois == 0 and camera.ia_enabled:
            camera.ia_status = 'ia_pending'
            camera.save()
        
        # Publica mensagem RabbitMQ roi.updated
        self.publish_roi_updated(camera)

    def publish_roi_updated(self, camera):
        """Publica mensagem na fila RabbitMQ roi.updated"""
        try:
            import pika
            import os
            
            rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
            connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
            channel = connection.channel()
            
            channel.queue_declare(queue='roi.updated', durable=True)
            
            rois = list(RegionOfInterest.objects.filter(
                camera=camera, active=True
            ).values('id', 'name', 'polygon', 'ia_type'))
            
            message = {
                'camera_id': str(camera.id),
                'roi_list': rois
            }
            
            channel.basic_publish(
                exchange='',
                routing_key='roi.updated',
                body=json.dumps(message, default=str)
            )
            
            connection.close()
        except Exception as e:
            print(f'Erro ao publicar roi.updated: {e}')

    @action(detail=False, methods=['get'], url_path='camera/(?P<camera_id>[^/.]+)/snapshot')
    def camera_snapshot(self, request, camera_id=None):
        """GET /api/v1/roi/camera/{camera_id}/snapshot/"""
        try:
            tenant_id = request.tenant_id
            camera = Camera.objects.get(id=camera_id, tenant_id=tenant_id)
            
            # Gera snapshot temporário (simulado - na prática chamaria MediaMTX)
            snapshot_url = f'/media/snapshots/{camera_id}.jpg'
            
            # Salva no Redis com TTL 30s
            cache_key = f'snapshot:{camera_id}'
            cache.set(cache_key, snapshot_url, 30)
            
            return Response({'url': snapshot_url})
        except Camera.DoesNotExist:
            return Response({'error': 'Camera not found'}, status=status.HTTP_404_NOT_FOUND)
