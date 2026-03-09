from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import camera_status, create_segment, expired_segments, delete_segment, ClipViewSet

router = DefaultRouter()
router.register('clips', ClipViewSet, basename='clip')

urlpatterns = [
    path('', include(router.urls)),
    path('internal/camera-status/', camera_status, name='camera-status'),
    path('internal/segments/', create_segment, name='create-segment'),
    path('internal/segments/expired/', expired_segments, name='expired-segments'),
    path('internal/segments/<uuid:pk>/', delete_segment, name='delete-segment'),
]
