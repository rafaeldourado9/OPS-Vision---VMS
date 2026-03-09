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
        
        # Verifica se usuário pertence ao tenant correto
        if user.tenant_id and str(user.tenant_id) != tenant_id:
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
    name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(source='active')

    def get_name(self, obj):
        return obj.email.split('@')[0]

    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'role', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
