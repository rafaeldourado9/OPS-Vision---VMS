from rest_framework import serializers
from .models import AIEvent


class AIEventSerializer(serializers.ModelSerializer):
    # Aliases para o frontend
    camera_id = serializers.UUIDField(read_only=True)
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    roi_id = serializers.SerializerMethodField()
    confidence = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    metadata = serializers.JSONField(source='event_data', read_only=True)

    class Meta:
        model = AIEvent
        fields = [
            'id', 'camera_id', 'camera_name', 'roi_id', 'event_type',
            'confidence', 'thumbnail_url', 'metadata',
            'detected_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_roi_id(self, obj):
        return str(obj.roi_id) if obj.roi_id else None

    def get_confidence(self, obj):
        if obj.event_data and isinstance(obj.event_data, dict):
            return obj.event_data.get('confidence')
        return None

    def get_thumbnail_url(self, obj):
        if not obj.snapshot_path:
            return None
        request = self.context.get('request')
        # Normaliza separadores de path (Windows usa \, URLs precisam de /)
        clean_path = obj.snapshot_path.replace('\\', '/')
        # Remove leading slash se já tiver, para evitar duplo /
        clean_path = clean_path.lstrip('/')
        path = f'/media/{clean_path}'
        if request:
            return request.build_absolute_uri(path)
        return path
