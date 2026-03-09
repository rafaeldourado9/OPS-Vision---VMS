from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils import timezone
from apps.cameras.models import Camera
from .models import Segment, Clip
from .serializers import SegmentSerializer, ClipSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def camera_status(request):
    """POST /api/v1/internal/camera-status/ - Chamado pelo MediaMTX"""
    camera_id = request.data.get('camera_id')
    status_value = request.data.get('status')
    
    try:
        camera = Camera.objects.get(id=camera_id)
        camera.online = (status_value == 'online')
        camera.last_seen = timezone.now()
        camera.save()
        
        return Response({'status': 'updated'})
    except Camera.DoesNotExist:
        return Response({'error': 'Camera not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_segment(request):
    """POST /api/v1/internal/segments/ - Chamado pelo Recorder Worker"""
    serializer = SegmentSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def expired_segments(request):
    """GET /api/v1/internal/segments/expired/ - Lista segmentos expirados"""
    segments = Segment.objects.filter(expires_at__lt=timezone.now())
    serializer = SegmentSerializer(segments, many=True)
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([AllowAny])
def delete_segment(request, pk):
    """DELETE /api/v1/internal/segments/{id}/ - Remove segmento"""
    try:
        segment = Segment.objects.get(pk=pk)
        segment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except Segment.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)


class ClipViewSet(viewsets.ModelViewSet):
    serializer_class = ClipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant_id = getattr(self.request, 'tenant_id', None)
        return Clip.objects.filter(camera__tenant_id=tenant_id)

    def perform_create(self, serializer):
        clip = serializer.save(created_by=self.request.user)
        
        # Publica na fila RabbitMQ para Clip Builder Worker
        import pika
        import json
        import os
        
        try:
            rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
            connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
            channel = connection.channel()
            
            channel.queue_declare(queue='clip.build', durable=True)
            
            message = {
                'clip_id': str(clip.id),
                'camera_id': str(clip.camera_id),
                'start_time': clip.start_time.isoformat(),
                'end_time': clip.end_time.isoformat()
            }
            
            channel.basic_publish(
                exchange='',
                routing_key='clip.build',
                body=json.dumps(message)
            )
            
            connection.close()
        except Exception as e:
            print(f'Erro ao publicar clip.build: {e}')
