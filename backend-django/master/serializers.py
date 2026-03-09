from rest_framework import serializers
from apps.resellers.models import Reseller
from apps.franchise.models import License
from apps.tenants.models import Tenant
from .models import AuditLog


class ResellerSerializer(serializers.ModelSerializer):
    """Serializer para CRUD de revendedores no painel master"""
    tenant_count = serializers.SerializerMethodField()

    class Meta:
        model = Reseller
        fields = [
            'id', 'name', 'slug', 'custom_domain',
            'primary_color', 'secondary_color',
            'logo_url', 'favicon_url', 'dark_mode_default',
            'terms_url', 'privacy_url',
            'active', 'created_at', 'tenant_count',
        ]
        read_only_fields = ['id', 'created_at']

    def get_tenant_count(self, obj):
        return obj.tenants.count()


class LicenseSerializer(serializers.ModelSerializer):
    """Serializer para licenças"""
    reseller_name = serializers.CharField(source='reseller.name', read_only=True)

    class Meta:
        model = License
        fields = [
            'id', 'reseller', 'reseller_name',
            'max_cameras', 'valid_until', 'active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class TenantSerializer(serializers.ModelSerializer):
    """Serializer para tenants/cidades"""
    reseller_name = serializers.CharField(source='reseller.name', read_only=True)
    camera_count = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            'id', 'reseller', 'reseller_name',
            'license', 'name', 'subdomain',
            'active', 'created_at', 'camera_count',
        ]
        read_only_fields = ['id', 'created_at']

    def get_camera_count(self, obj):
        return obj.cameras.count()


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer para logs de auditoria (somente leitura)"""
    user_email = serializers.CharField(source='user.email', read_only=True)
    tenant_name = serializers.CharField(source='target_tenant.name', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_email', 'action',
            'target_tenant', 'tenant_name',
            'details', 'ip_address', 'created_at',
        ]
        read_only_fields = fields


class ImpersonateSerializer(serializers.Serializer):
    """Serializer para validação de impersonação"""
    tenant_id = serializers.UUIDField()
