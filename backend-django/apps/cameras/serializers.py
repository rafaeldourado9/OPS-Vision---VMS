from rest_framework import serializers
from .models import Camera


class CameraSerializer(serializers.ModelSerializer):
    # Compatibility aliases for the React frontend (read-only)
    location = serializers.CharField(source='address', read_only=True)
    status = serializers.SerializerMethodField()
    recording_retention_days = serializers.IntegerField(source='retention_days', read_only=True)
    ai_enabled = serializers.BooleanField(source='ia_enabled', read_only=True)
    protocol = serializers.CharField(source='stream_protocol', read_only=True)
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

    def get_status(self, obj):
        return 'online' if obj.online else 'offline'

    def get_latitude(self, obj):
        return float(obj.latitude) if obj.latitude is not None else None

    def get_longitude(self, obj):
        return float(obj.longitude) if obj.longitude is not None else None

    def get_thumbnail_url(self, obj):
        return None

    def get_snapshot_url(self, obj):
        return None

    def get_stream_url_frontend(self, obj):
        request = self.context.get('request')
        if request:
            host = request.get_host().split(':')[0]
            tenant_id = getattr(request, 'tenant_id', None)
            if tenant_id:
                return f'http://{host}:8888/live/{tenant_id}/{obj.id}/index.m3u8'
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
            'id', 'name', 'address', 'location', 'latitude', 'longitude',
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
        # RTSP requer stream_url
        if attrs.get('stream_protocol') == 'rtsp' and not attrs.get('stream_url'):
            raise serializers.ValidationError({
                'stream_url': 'stream_url é obrigatório para protocolo RTSP'
            })

        return attrs
