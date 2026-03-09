from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegionOfInterestViewSet

router = DefaultRouter()
router.register('roi', RegionOfInterestViewSet, basename='roi')

urlpatterns = [
    path('', include(router.urls)),
]
