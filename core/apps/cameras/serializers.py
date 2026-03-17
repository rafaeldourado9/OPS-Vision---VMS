"""Serializers para câmeras."""
import re

from rest_framework import serializers

from .models import Camera

RTSP_URL_PATTERN = re.compile(
    r"^rtsp://[^\s/$.?#].[^\s]*$", re.IGNORECASE
)


class RTSPURLField(serializers.CharField):
    """Campo que valida URLs RTSP (rtsp://)."""

    def to_internal_value(self, data: str) -> str:
        """Valida formato da URL RTSP."""
        value = super().to_internal_value(data)
        if not RTSP_URL_PATTERN.match(value):
            raise serializers.ValidationError(
                "URL RTSP inválida. Use o formato: rtsp://host:porta/path"
            )
        return value


class CameraSerializer(serializers.ModelSerializer):
    """Serializer completo para Camera."""

    class Meta:
        model = Camera
        fields = [
            "id",
            "name",
            "location",
            "rtsp_url",
            "manufacturer",
            "retention_days",
            "is_online",
            "agent",
            "tenant",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_online", "agent", "tenant", "created_at", "updated_at"]


class CameraCreateSerializer(serializers.Serializer):
    """Serializer para criação de câmera."""

    name = serializers.CharField(max_length=255)
    location = serializers.CharField(max_length=255)
    # rtsp_url é opcional — câmeras RTMP push não têm URL RTSP
    rtsp_url = RTSPURLField(required=False, allow_blank=True, default="")
    manufacturer = serializers.ChoiceField(
        choices=Camera.Manufacturer.choices,
        default=Camera.Manufacturer.OTHER,
    )
    retention_days = serializers.ChoiceField(
        choices=Camera.RetentionDays.choices,
        default=Camera.RetentionDays.SEVEN,
    )
    agent_id = serializers.IntegerField(required=False, allow_null=True, default=None)


class LiveStreamSerializer(serializers.Serializer):
    """Serializer para resposta do endpoint /live/."""

    camera_id = serializers.IntegerField()
    is_online = serializers.BooleanField()
    hls_url = serializers.CharField()
    webrtc_url = serializers.CharField()
    token = serializers.CharField(allow_blank=True)
    expires_at = serializers.DateTimeField(allow_null=True)


class PushConfigSerializer(serializers.Serializer):
    """Serializer para resposta do endpoint /push-config/."""

    rtmp_url   = serializers.CharField()
    stream_key = serializers.CharField()
    username   = serializers.CharField()
    password   = serializers.CharField()
    full_url   = serializers.CharField()


class CameraUpdateSerializer(serializers.Serializer):
    """Serializer para atualização de câmera."""

    name = serializers.CharField(max_length=255, required=False)
    location = serializers.CharField(max_length=255, required=False)
    rtsp_url = RTSPURLField(required=False)
    manufacturer = serializers.ChoiceField(
        choices=Camera.Manufacturer.choices,
        required=False,
    )
    retention_days = serializers.ChoiceField(
        choices=Camera.RetentionDays.choices,
        required=False,
    )
