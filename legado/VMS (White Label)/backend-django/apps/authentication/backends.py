from django.contrib.auth.backends import ModelBackend
from apps.auth_app.models import User
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class QueryStringJWTAuthentication(JWTAuthentication):
    """Permite autenticação via ?token= na query string (para img.src, etc.)"""

    def authenticate(self, request):
        token = request.query_params.get('token') or request.GET.get('token')
        if not token:
            return super().authenticate(request)
        try:
            validated = self.get_validated_token(self.get_raw_token(f'Bearer {token}'.encode()))
            return self.get_user(validated), validated
        except (InvalidToken, TokenError):
            return None


class EmailBackend(ModelBackend):
    """Backend de autenticação por email"""
    
    def authenticate(self, request, email=None, password=None, **kwargs):
        try:
            user = User.objects.get(email=email, active=True)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
