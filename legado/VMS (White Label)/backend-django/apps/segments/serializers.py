from rest_framework import serializers
from .models import Segment, Clip, StoragePolicy, StorageFile

STATUS_MAP = {'completed': 'ready', 'failed': 'error'}


class SegmentSerializer(serializers.ModelSerializer):
    started_at = serializers.DateTimeField(source='start_time', read_only=True)
    ended_at = serializers.DateTimeField(source='end_time', read_only=True)
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = Segment
        fields = [
            'id', 'camera',
            'started_at', 'ended_at', 'duration_seconds',
            'start_time', 'end_time',
            'file_path', 'file_size', 'expires_at', 'created_at',
        ]
        read_only_fields = ['id', 'expires_at', 'created_at']

    def get_duration_seconds(self, obj):
        if obj.start_time and obj.end_time:
            return int((obj.end_time - obj.start_time).total_seconds())
        return None


class ClipSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    started_at = serializers.DateTimeField(source='start_time', read_only=True)
    ended_at = serializers.DateTimeField(source='end_time', read_only=True)
    file_url = serializers.SerializerMethodField()
    duration_seconds = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Clip
        fields = [
            'id', 'camera', 'camera_name', 'name',
            'started_at', 'ended_at',
            'start_time', 'end_time',
            'file_url', 'file_size',
            'duration_seconds', 'status', 'created_at',
        ]
        read_only_fields = ['id', 'file_size', 'created_at']
        extra_kwargs = {
            'start_time': {'write_only': True, 'required': False},
            'end_time': {'write_only': True, 'required': False},
        }

    def to_internal_value(self, data):
        # Aceita started_at/ended_at como aliases de start_time/end_time
        data = data.copy()
        if 'started_at' in data and 'start_time' not in data:
            data['start_time'] = data.pop('started_at')
        if 'ended_at' in data and 'end_time' not in data:
            data['end_time'] = data.pop('ended_at')
        return super().to_internal_value(data)

    def get_file_url(self, obj):
        if not obj.file_path:
            return None
        request = self.context.get('request')
        path = f'/media/{obj.file_path}'
        return request.build_absolute_uri(path) if request else path

    def get_duration_seconds(self, obj):
        if obj.start_time and obj.end_time:
            return int((obj.end_time - obj.start_time).total_seconds())
        return None

    def get_status(self, obj):
        return STATUS_MAP.get(obj.status, obj.status)


class StoragePolicySerializer(serializers.ModelSerializer):
    max_age_display = serializers.SerializerMethodField()

    class Meta:
        model = StoragePolicy
        fields = [
            'id', 'tenant', 'category', 'tier_order', 'path',
            'max_age_hours', 'max_size_gb', 'enabled',
            'max_age_display', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_max_age_display(self, obj):
        if not obj.max_age_hours:
            return None
        days = obj.max_age_hours // 24
        hours = obj.max_age_hours % 24
        if days and hours:
            return f"{days}d {hours}h"
        if days:
            return f"{days}d"
        return f"{hours}h"


class StorageFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorageFile
        fields = [
            'id', 'tenant', 'camera', 'category', 'subcategory',
            'file_path', 'file_size', 'tier_order', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class StorageStatsSerializer(serializers.Serializer):
    """Estatísticas de uso de storage por categoria."""
    category = serializers.CharField()
    tier_order = serializers.IntegerField()
    total_files = serializers.IntegerField()
    total_size_bytes = serializers.IntegerField()
    total_size_display = serializers.CharField()
    oldest_file = serializers.DateTimeField(allow_null=True)
    newest_file = serializers.DateTimeField(allow_null=True)
