"""Serializers para agents."""
from rest_framework import serializers

from .models import Agent


class AgentSerializer(serializers.ModelSerializer):
    """Serializer completo para Agent (leitura)."""

    class Meta:
        model = Agent
        fields = [
            "id",
            "name",
            "tenant",
            "status",
            "last_heartbeat",
            "version",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AgentCreateSerializer(serializers.Serializer):
    """Serializer para criação de agent."""

    name = serializers.CharField(max_length=255)


class AgentCreateResponseSerializer(serializers.Serializer):
    """Serializer para resposta de criação (inclui api_key)."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    api_key = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class CameraConfigSerializer(serializers.Serializer):
    """Serializer para configuração de câmera no agent."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    rtsp_url = serializers.CharField()
    rtmp_push_url = serializers.CharField()
    enabled = serializers.BooleanField()


class AgentConfigResponseSerializer(serializers.Serializer):
    """Serializer para resposta de configuração do agent."""

    agent_id = serializers.IntegerField()
    tenant_id = serializers.IntegerField()
    poll_interval_seconds = serializers.IntegerField()
    cameras = CameraConfigSerializer(many=True)


class HeartbeatSerializer(serializers.Serializer):
    """Serializer para heartbeat do agent."""

    version = serializers.CharField(max_length=32)
    uptime_seconds = serializers.IntegerField(min_value=0)
    cameras = serializers.DictField(default=dict)
