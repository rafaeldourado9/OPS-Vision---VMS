"""URLs para autenticação e usuário."""
from django.urls import path

from .views import UserMeView

urlpatterns = [
    path("auth/me/", UserMeView.as_view(), name="user-me"),
]
