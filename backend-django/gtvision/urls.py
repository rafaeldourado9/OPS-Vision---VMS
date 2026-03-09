from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.resellers.urls')),
    path('api/v1/', include('apps.authentication.urls')),
    path('api/v1/', include('apps.cameras.urls')),
    path('api/v1/', include('apps.segments.urls')),
    path('api/v1/', include('apps.roi.urls')),
    path('api/v1/', include('apps.detections.urls')),
    path('master/', include('master.urls')),
]
