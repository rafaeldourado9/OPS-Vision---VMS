"""Serializers para users e tenants."""
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Tenant

User = get_user_model()


class TenantSerializer(serializers.ModelSerializer):
    """Serializer resumido do tenant para embutir na resposta do usuário."""

    class Meta:
        model = Tenant
        fields = ["id", "name", "slug"]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    """Serializer para o usuário autenticado."""

    tenant = TenantSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "tenant"]
        read_only_fields = fields
