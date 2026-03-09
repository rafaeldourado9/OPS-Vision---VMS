from rest_framework import serializers
from .models import Segment, Clip


class SegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segment
        fields = ['id', 'camera', 'start_time', 'end_time', 'file_path', 'file_size', 'expires_at', 'created_at']
        read_only_fields = ['id', 'expires_at', 'created_at']


class ClipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clip
        fields = ['id', 'camera', 'name', 'start_time', 'end_time', 'file_path', 'file_size', 'status', 'created_at']
        read_only_fields = ['id', 'file_path', 'file_size', 'status', 'created_at']
