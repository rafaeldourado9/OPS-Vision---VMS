from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CameraViewSet, DetectionMaskViewSet

router = DefaultRouter()
router.register('cameras', CameraViewSet, basename='camera')
router.register('detection-masks', DetectionMaskViewSet, basename='detection-mask')

urlpatterns = [
    path('', include(router.urls)),
]
