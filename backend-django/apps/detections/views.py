from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.db.models import Q
import csv
from datetime import datetime
from .models import AIEvent
from .serializers import AIEventSerializer


class AIEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AIEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtra eventos por tenant com filtros opcionais"""
        tenant_id = getattr(self.request, 'tenant_id', None)
        queryset = AIEvent.objects.filter(tenant_id=tenant_id)
        
        # Filtros
        camera_id = self.request.query_params.get('camera_id')
        if camera_id:
            queryset = queryset.filter(camera_id=camera_id)
        
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        # Suporta start_date/end_date e started_after/started_before (alias frontend)
        start_date = self.request.query_params.get('start_date') or self.request.query_params.get('started_after')
        if start_date:
            queryset = queryset.filter(detected_at__gte=start_date)

        end_date = self.request.query_params.get('end_date') or self.request.query_params.get('started_before')
        if end_date:
            queryset = queryset.filter(detected_at__lte=end_date)
        
        plate = self.request.query_params.get('plate')
        if plate:
            queryset = queryset.filter(event_data__plate__icontains=plate)
        
        return queryset

    @action(detail=False, methods=['get'])
    def export(self, request):
        """GET /api/v1/detections/export/?file_format=csv"""
        format_type = request.query_params.get('file_format', 'csv')
        
        if format_type != 'csv':
            return Response({'error': 'Apenas CSV suportado'}, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = self.get_queryset()
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="detections_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['ID', 'Câmera', 'Tipo', 'Placa', 'Confiança', 'Data/Hora'])
        
        for event in queryset:
            plate = event.event_data.get('plate', '-')
            confidence = event.event_data.get('confidence', '-')
            writer.writerow([
                str(event.id),
                event.camera.name,
                event.get_event_type_display(),
                plate,
                confidence,
                event.detected_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
