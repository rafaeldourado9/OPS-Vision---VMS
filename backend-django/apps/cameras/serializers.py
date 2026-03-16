from rest_framework import serializers
from .models import Camera, DetectionMask


class CameraSerializer(serializers.ModelSerializer):
    # Compatibility aliases for the React frontend (read-only)
    location = serializers.CharField(source='address', read_only=True)
    status = serializers.SerializerMethodField()
    recording_retention_days = serializers.IntegerField(source='retention_days', read_only=True)
    ai_enabled = serializers.BooleanField(source='ia_enabled', read_only=True)
    protocol = serializers.CharField(source='stream_protocol', read_only=True)
    # Aliases lat/lng para compatibilidade com o frontend (leitura via method, escrita via FloatField)
    lat = serializers.FloatField(write_only=True, required=False, default=0)
    lng = serializers.FloatField(write_only=True, required=False, default=0)
    # Mantém latitude/longitude para compatibilidade retroativa
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    snapshot_url = serializers.SerializerMethodField()
    stream_url_frontend = serializers.SerializerMethodField()
    ai_websocket_url = serializers.SerializerMethodField()
    mediamtx_path = serializers.SerializerMethodField()
    roi_areas = serializers.SerializerMethodField()
    virtual_lines = serializers.SerializerMethodField()
    tripwires = serializers.SerializerMethodField()
    zone_triggers = serializers.SerializerMethodField()
    recording_enabled = serializers.SerializerMethodField()
    detection_settings = serializers.SerializerMethodField()

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Adiciona lat/lng na leitura para o frontend
        rep['lat'] = float(instance.latitude) if instance.latitude is not None else None
        rep['lng'] = float(instance.longitude) if instance.longitude is not None else None
        return rep

    def get_status(self, obj):
        return 'online' if obj.online else 'offline'

    def get_lat(self, obj):
        return float(obj.latitude) if obj.latitude is not None else None

    def get_lng(self, obj):
        return float(obj.longitude) if obj.longitude is not None else None

    def get_latitude(self, obj):
        return float(obj.latitude) if obj.latitude is not None else None

    def get_longitude(self, obj):
        return float(obj.longitude) if obj.longitude is not None else None

    def get_thumbnail_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/api/v1/cameras/{obj.id}/thumbnail/')
        return None

    def get_snapshot_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/api/v1/cameras/{obj.id}/thumbnail/')
        return None

    def get_stream_url_frontend(self, obj):
        request = self.context.get('request')
        if request:
            host = request.get_host().split(':')[0]
            tenant_id = getattr(request, 'tenant_id', None)
            if tenant_id:
                return f'http://{host}/hls/live/{tenant_id}/{obj.id}/index.m3u8'
        return None

    def get_ai_websocket_url(self, obj):
        return None

    def get_mediamtx_path(self, obj):
        request = self.context.get('request')
        if request:
            tenant_id = getattr(request, 'tenant_id', None)
            if tenant_id:
                return f'live/{tenant_id}/{obj.id}'
        return None

    def get_roi_areas(self, obj):
        return []

    def get_virtual_lines(self, obj):
        return []

    def get_tripwires(self, obj):
        return []

    def get_zone_triggers(self, obj):
        return []

    def get_recording_enabled(self, obj):
        return True

    def get_detection_settings(self, obj):
        return {}

    class Meta:
        model = Camera
        fields = [
            'id', 'name', 'address', 'location', 'lat', 'lng', 'latitude', 'longitude',
            'stream_protocol', 'protocol', 'stream_url', 'stream_key',
            'stream_url_frontend', 'ai_websocket_url', 'mediamtx_path',
            'retention_days', 'recording_retention_days', 'recording_enabled',
            'ia_enabled', 'ai_enabled', 'ia_status',
            'online', 'status', 'last_seen', 'created_at',
            'thumbnail_url', 'snapshot_url',
            'roi_areas', 'virtual_lines', 'tripwires', 'zone_triggers',
            'detection_settings',
        ]
        read_only_fields = ['id', 'stream_key', 'ia_status', 'online', 'last_seen', 'created_at']

    def validate(self, attrs):
        # Aceita lat/lng do frontend e mapeia para latitude/longitude do modelo
        if 'lat' in attrs:
            attrs['latitude'] = attrs.pop('lat')
        if 'lng' in attrs:
            attrs['longitude'] = attrs.pop('lng')

        # Garante defaults para latitude/longitude
        if 'latitude' not in attrs:
            attrs['latitude'] = 0
        if 'longitude' not in attrs:
            attrs['longitude'] = 0

        # RTSP requer stream_url
        if attrs.get('stream_protocol') == 'rtsp' and not attrs.get('stream_url'):
            raise serializers.ValidationError({
                'stream_url': 'stream_url é obrigatório para protocolo RTSP'
            })

        return attrs


class DetectionMaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetectionMask
        fields = [
            'id', 'tenant', 'camera', 'polygon', 'active',
            'created_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at']

    def validate_polygon(self, value):
        if not isinstance(value, list) or len(value) < 3:
            raise serializers.ValidationError('Polígono precisa de pelo menos 3 pontos')
        for point in value:
            if not isinstance(point, list) or len(point) != 2:
                raise serializers.ValidationError('Cada ponto deve ser [x, y]')
            x, y = point
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise serializers.ValidationError('Coordenadas devem estar entre 0 e 1')
        return value
