from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

from apps.roi.internal_views import RoiSyncView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/internal/roi-sync/', RoiSyncView.as_view(), name='internal-roi-sync'),
    path('api/v1/', include('apps.resellers.urls')),
    path('api/v1/', include('apps.authentication.urls')),
    path('api/v1/', include('apps.cameras.urls')),
    path('api/v1/', include('apps.segments.urls')),
    path('api/v1/', include('apps.roi.urls')),
    path('api/v1/', include('apps.detections.urls')),
    path('api/v1/', include('apps.dashboard.urls')),
    path('api/v1/', include('apps.persons.urls')),
    path('master/', include('master.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
