from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AIEventViewSet

router = DefaultRouter()
router.register('detections', AIEventViewSet, basename='detection')

urlpatterns = [
    path('', include(router.urls)),
]
