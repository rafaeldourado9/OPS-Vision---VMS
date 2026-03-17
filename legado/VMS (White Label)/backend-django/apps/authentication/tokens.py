from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Adiciona claims customizados
        token['user_id'] = str(user.id)
        token['tenant_id'] = str(user.tenant_id) if user.tenant_id else None
        token['role'] = user.role
        
        return token
