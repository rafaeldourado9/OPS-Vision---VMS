from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import KnownPersonViewSet, InternalPersonsView

router = DefaultRouter()
router.register(r'persons', KnownPersonViewSet, basename='persons')

urlpatterns = [
    path('', include(router.urls)),
    path('internal/persons/', InternalPersonsView.as_view(), name='internal-persons'),
]
