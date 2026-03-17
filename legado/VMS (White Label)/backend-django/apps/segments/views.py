from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils import timezone
from django.db.models import Count, Sum, Min, Max
from apps.cameras.models import Camera
from .models import Segment, Clip, StoragePolicy, StorageFile
from .serializers import (
    SegmentSerializer, ClipSerializer,
    StoragePolicySerializer, StorageFileSerializer, StorageStatsSerializer,
)


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
    # Accept both 'camera' (new) and 'camera_id' (legacy) field names
    data = request.data.copy()
    if 'camera_id' in data and 'camera' not in data:
        data['camera'] = data['camera_id']
    serializer = SegmentSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    # Log detalhado do erro para debug
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f'Segment validation failed: {serializer.errors} | Data: {request.data}')
    
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


class SegmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SegmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant_id = getattr(self.request, 'tenant_id', None)
        qs = Segment.objects.filter(camera__tenant_id=tenant_id)
        camera_id = self.request.query_params.get('camera_id')
        if camera_id:
            qs = qs.filter(camera_id=camera_id)
        date = self.request.query_params.get('date')
        if date:
            qs = qs.filter(start_time__date=date)
        return qs


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


# ---------------------------------------------------------------------------
# Storage Policy CRUD
# ---------------------------------------------------------------------------

class StoragePolicyViewSet(viewsets.ModelViewSet):
    serializer_class = StoragePolicySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant_id = getattr(self.request, 'tenant_id', None)
        return StoragePolicy.objects.filter(tenant_id=tenant_id)

    def perform_create(self, serializer):
        tenant_id = getattr(self.request, 'tenant_id', None)
        serializer.save(tenant_id=tenant_id)


# ---------------------------------------------------------------------------
# Internal: File tracking (chamado pelos workers)
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def register_storage_file(request):
    """POST /api/v1/internal/storage-files/ — Workers registram snapshots/heatmaps."""
    serializer = StorageFileSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def bulk_register_storage_files(request):
    """POST /api/v1/internal/storage-files/bulk/ — Registro em lote."""
    files_data = request.data if isinstance(request.data, list) else request.data.get('files', [])
    created = []
    for item in files_data:
        serializer = StorageFileSerializer(data=item)
        if serializer.is_valid():
            serializer.save()
            created.append(serializer.data)
    return Response({'created': len(created)}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Internal: Purge endpoints (chamados pelo purge-worker)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([AllowAny])
def storage_policies_all(request):
    """GET /api/v1/internal/storage/policies/ — Todas as policies ativas."""
    policies = StoragePolicy.objects.filter(enabled=True).select_related('tenant')
    serializer = StoragePolicySerializer(policies, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def storage_stats(request):
    """GET /api/v1/internal/storage/stats/ — Estatísticas de uso por categoria/tier."""

    def sizeof_fmt(num):
        for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
            if abs(num) < 1024:
                return f"{num:.1f} {unit}"
            num /= 1024
        return f"{num:.1f} PB"

    # Segments
    seg_stats = (
        Segment.objects.values('tier_order')
        .annotate(
            total_files=Count('id'),
            total_size_bytes=Sum('file_size'),
            oldest_file=Min('created_at'),
            newest_file=Max('created_at'),
        )
    )
    results = []
    for s in seg_stats:
        results.append({
            'category': 'recordings',
            'tier_order': s['tier_order'],
            'total_files': s['total_files'],
            'total_size_bytes': s['total_size_bytes'] or 0,
            'total_size_display': sizeof_fmt(s['total_size_bytes'] or 0),
            'oldest_file': s['oldest_file'],
            'newest_file': s['newest_file'],
        })

    # StorageFiles (snapshots, heatmaps, clips)
    sf_stats = (
        StorageFile.objects.values('category', 'tier_order')
        .annotate(
            total_files=Count('id'),
            total_size_bytes=Sum('file_size'),
            oldest_file=Min('created_at'),
            newest_file=Max('created_at'),
        )
    )
    for s in sf_stats:
        results.append({
            'category': s['category'],
            'tier_order': s['tier_order'],
            'total_files': s['total_files'],
            'total_size_bytes': s['total_size_bytes'] or 0,
            'total_size_display': sizeof_fmt(s['total_size_bytes'] or 0),
            'oldest_file': s['oldest_file'],
            'newest_file': s['newest_file'],
        })

    return Response(results)


@api_view(['POST'])
@permission_classes([AllowAny])
def purge_expired_segments(request):
    """POST /api/v1/internal/storage/purge-segments/ — Remove segments expirados em batch."""
    batch_size = int(request.data.get('batch_size', 500))
    expired = Segment.objects.filter(
        expires_at__lt=timezone.now()
    ).order_by('expires_at')[:batch_size]

    paths = []
    ids = []
    for seg in expired:
        paths.append(seg.file_path)
        ids.append(seg.id)

    deleted_count = Segment.objects.filter(id__in=ids).delete()[0]
    return Response({
        'deleted_db': deleted_count,
        'file_paths': paths,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def purge_old_storage_files(request):
    """POST /api/v1/internal/storage/purge-files/ — Remove storage_files antigos em batch."""
    category = request.data.get('category')
    max_age_hours = int(request.data.get('max_age_hours', 168))
    batch_size = int(request.data.get('batch_size', 500))

    cutoff = timezone.now() - timezone.timedelta(hours=max_age_hours)
    qs = StorageFile.objects.filter(created_at__lt=cutoff)
    if category:
        qs = qs.filter(category=category)
    qs = qs.order_by('created_at')[:batch_size]

    paths = []
    ids = []
    for sf in qs:
        paths.append(sf.file_path)
        ids.append(sf.id)

    deleted_count = StorageFile.objects.filter(id__in=ids).delete()[0]
    return Response({
        'deleted_db': deleted_count,
        'file_paths': paths,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def purge_old_events(request):
    """POST /api/v1/internal/storage/purge-events/ — Remove AIEvents antigos."""
    from apps.detections.models import AIEvent

    max_age_days = int(request.data.get('max_age_days', 30))
    batch_size = int(request.data.get('batch_size', 1000))

    cutoff = timezone.now() - timezone.timedelta(days=max_age_days)
    old_events = AIEvent.objects.filter(detected_at__lt=cutoff).order_by('detected_at')[:batch_size]

    paths = [e.snapshot_path for e in old_events if e.snapshot_path]
    ids = [e.id for e in old_events]

    deleted_count = AIEvent.objects.filter(id__in=ids).delete()[0]
    return Response({
        'deleted_db': deleted_count,
        'snapshot_paths': paths,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def tier_move_segments(request):
    """POST /api/v1/internal/storage/tier-move-segments/
    Retorna segments a mover do tier_from baseado em policy."""
    tier_from = int(request.data.get('tier_from', 0))
    tenant_id = request.data.get('tenant_id')
    max_age_hours = request.data.get('max_age_hours')
    max_size_bytes = request.data.get('max_size_bytes')
    batch_size = int(request.data.get('batch_size', 200))

    qs = Segment.objects.filter(tier_order=tier_from)
    if tenant_id:
        qs = qs.filter(camera__tenant_id=tenant_id)

    to_move = []

    # Critério 1: idade
    if max_age_hours:
        cutoff = timezone.now() - timezone.timedelta(hours=int(max_age_hours))
        age_qs = qs.filter(created_at__lt=cutoff).order_by('created_at')[:batch_size]
        to_move.extend([{
            'id': str(s.id), 'file_path': s.file_path, 'file_size': s.file_size,
        } for s in age_qs])

    # Critério 2: tamanho total do tier
    if max_size_bytes and len(to_move) < batch_size:
        total = qs.aggregate(total=Sum('file_size'))['total'] or 0
        if total > int(max_size_bytes):
            excess = total - int(max_size_bytes)
            overflow_qs = qs.order_by('created_at')
            collected = 0
            for s in overflow_qs.iterator():
                if collected >= excess or len(to_move) >= batch_size:
                    break
                entry = {'id': str(s.id), 'file_path': s.file_path, 'file_size': s.file_size}
                if entry not in to_move:
                    to_move.append(entry)
                    collected += s.file_size

    return Response({'segments': to_move[:batch_size]})


@api_view(['POST'])
@permission_classes([AllowAny])
def tier_confirm_move(request):
    """POST /api/v1/internal/storage/tier-confirm-move/
    Confirma que o purge-worker moveu/deletou os arquivos, atualiza tier_order."""
    items = request.data.get('items', [])
    new_tier = request.data.get('new_tier')
    delete = request.data.get('delete', False)

    segment_ids = [i['id'] for i in items if i.get('type', 'segment') == 'segment']
    file_ids = [i['id'] for i in items if i.get('type') == 'storage_file']

    updated = 0
    if delete:
        updated += Segment.objects.filter(id__in=segment_ids).delete()[0]
        updated += StorageFile.objects.filter(id__in=file_ids).delete()[0]
    else:
        updated += Segment.objects.filter(id__in=segment_ids).update(tier_order=new_tier)
        updated += StorageFile.objects.filter(id__in=file_ids).update(tier_order=new_tier)

    return Response({'updated': updated})
