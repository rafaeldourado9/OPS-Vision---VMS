from django.urls import path
from .views import get_theme

urlpatterns = [
    path('theme/', get_theme, name='get-theme'),
]
