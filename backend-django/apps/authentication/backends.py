from django.contrib.auth.backends import ModelBackend
from apps.auth_app.models import User


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
