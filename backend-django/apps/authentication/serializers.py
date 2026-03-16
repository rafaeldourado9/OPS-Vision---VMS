from rest_framework import serializers
from django.contrib.auth import authenticate
from django.core.cache import cache
from apps.auth_app.models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        # Verifica rate limit
        rate_key = f'rate_limit:login:{email}'
        attempts = cache.get(rate_key, 0)
        
        if attempts >= 5:
            raise serializers.ValidationError({
                'detail': 'Conta temporariamente bloqueada. Tente novamente em 15 minutos.'
            }, code='account_locked')
        
        # Verifica tenant do request
        request = self.context.get('request')
        tenant_id = getattr(request, 'tenant_id', None)
        
        user = authenticate(email=email, password=password)
        
        if not user:
            # Incrementa tentativas falhas
            cache.set(rate_key, attempts + 1, 900)  # 15 minutos
            raise serializers.ValidationError({
                'detail': 'Email ou senha incorretos.'
            }, code='invalid_credentials')
        
        # Verifica se usuário pertence ao tenant correto (skip se tenant_id não resolvido)
        if user.tenant_id and tenant_id is not None and str(user.tenant_id) != tenant_id:
            raise serializers.ValidationError({
                'detail': 'Email ou senha incorretos.'
            }, code='invalid_credentials')
        
        # Limpa rate limit em caso de sucesso
        cache.delete(rate_key)
        
        attrs['user'] = user
        return attrs


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(min_length=8, write_only=True)


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(source='active', required=False)

    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'role', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

    def to_representation(self, obj):
        rep = super().to_representation(obj)
        if not rep.get('name'):
            rep['name'] = obj.email.split('@')[0]
        return rep


class UserCreateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, default='')
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    role = serializers.ChoiceField(
        choices=['operator', 'supervisor', 'city_admin', 'reseller_admin', 'super_admin'],
        default='operator',
    )
    is_active = serializers.BooleanField(default=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email já cadastrado.')
        return value

    def create(self, validated_data):
        validated_data.pop('name', '')
        is_active = validated_data.pop('is_active', True)
        password = validated_data.pop('password')
        tenant_id = validated_data.pop('tenant_id', None)
        return User.objects.create_user(
            **validated_data,
            password=password,
            active=is_active,
            tenant_id=tenant_id,
        )
