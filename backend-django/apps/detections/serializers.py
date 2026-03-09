from rest_framework import serializers
from .models import AIEvent


class AIEventSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    
    class Meta:
        model = AIEvent
        fields = [
            'id', 'camera', 'camera_name', 'roi', 'event_type',
            'snapshot_path', 'event_data', 'detected_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
