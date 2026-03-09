from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ResellerViewSet, LicenseViewSet,
    TenantViewSet, AuditLogViewSet,
    metrics, impersonate,
)

router = DefaultRouter()
router.register('resellers', ResellerViewSet, basename='master-reseller')
router.register('licenses', LicenseViewSet, basename='master-license')
router.register('tenants', TenantViewSet, basename='master-tenant')
router.register('audit-logs', AuditLogViewSet, basename='master-audit')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/metrics/', metrics, name='master-metrics'),
    path('api/impersonate/<uuid:tenant_id>/', impersonate, name='master-impersonate'),
]
