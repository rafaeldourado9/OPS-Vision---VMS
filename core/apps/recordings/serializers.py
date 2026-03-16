import os

from rest_framework import serializers

from .models import Clip


class ClipSerializer(serializers.ModelSerializer):
    """Serializer para listagem e detalhe de clip."""

    camera_name = serializers.CharField(source="camera.name", read_only=True)
    started_at = serializers.DateTimeField(source="start_time", read_only=True)
    ended_at = serializers.DateTimeField(source="end_time", read_only=True)
    file_size_bytes = serializers.SerializerMethodField()

    class Meta:
        model = Clip
        fields = [
            "id",
            "status",
            "camera_id",
            "camera_name",
            "started_at",
            "ended_at",
            "file_path",
            "file_size_bytes",
            "created_at",
        ]
        read_only_fields = fields

    def get_file_size_bytes(self, obj: Clip) -> int | None:
        """Retorna o tamanho do arquivo em bytes, ou None se não disponível."""
        if obj.file_path and os.path.exists(obj.file_path):
            return os.path.getsize(obj.file_path)
        return None


class TimelineSegmentSerializer(serializers.Serializer):
    """Serializer para segmentos da linha do tempo da câmera."""
    id = serializers.IntegerField()
    start = serializers.DateTimeField(source="start_time")
    end = serializers.DateTimeField(source="end_time")
    duration_seconds = serializers.IntegerField()


class ClipCreateSerializer(serializers.Serializer):
    """Serializer para criação de clip via seleção de intervalo."""
    camera_id = serializers.IntegerField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()

    def validate(self, data: dict) -> dict:
        if data["end_time"] <= data["start_time"]:
            raise serializers.ValidationError(
                "end_time deve ser posterior a start_time."
            )
        return data


class PlaybackResponseSerializer(serializers.Serializer):
    """Serializer para resposta de playback."""
    camera_id = serializers.IntegerField()
    segment_start = serializers.DateTimeField()
    segment_end = serializers.DateTimeField()
    offset_seconds = serializers.FloatField()
    file_path = serializers.CharField()


class ClipCreateResponseSerializer(serializers.Serializer):
    """Serializer para resposta de criação de clip."""
    clip_id = serializers.IntegerField()
    status = serializers.CharField()
