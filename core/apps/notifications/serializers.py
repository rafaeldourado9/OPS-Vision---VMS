"""Serializers para o app de notificações."""
from rest_framework import serializers

from .models import NotificationLog, NotificationRule


class NotificationRuleSerializer(serializers.ModelSerializer):
    """Serializer para regras de notificação.

    O `tenant` é definido automaticamente na view.
    """

    class Meta:
        model = NotificationRule
        fields = (
            "id",
            "name",
            "event_type_pattern",
            "channel",
            "destination",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def create(self, validated_data):
        """Associa o tenant do usuário logado à regra."""
        request = self.context.get("request")
        if request and hasattr(request.user, "tenant"):
            validated_data["tenant"] = request.user.tenant
        return super().create(validated_data)


class NotificationLogSerializer(serializers.ModelSerializer):
    """Serializer para logs de notificação (apenas leitura)."""

    rule_name = serializers.CharField(source="rule.name", read_only=True)

    class Meta:
        model = NotificationLog
        fields = (
            "id",
            "rule",
            "rule_name",
            "event_id",
            "event_type",
            "status",
            "response_code",
            "response_body",
            "created_at",
        )
        read_only_fields = fields
