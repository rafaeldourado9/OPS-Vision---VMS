from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    camera_status, create_segment, expired_segments, delete_segment,
    ClipViewSet, SegmentViewSet, StoragePolicyViewSet,
    register_storage_file, bulk_register_storage_files,
    storage_policies_all, storage_stats,
    purge_expired_segments, purge_old_storage_files, purge_old_events,
    tier_move_segments, tier_confirm_move,
)

router = DefaultRouter()
router.register('segments', SegmentViewSet, basename='segment')
router.register('clips', ClipViewSet, basename='clip')
router.register('storage-policies', StoragePolicyViewSet, basename='storage-policy')

urlpatterns = [
    path('', include(router.urls)),
    # Internal (chamados por workers, sem auth)
    path('internal/camera-status/', camera_status, name='camera-status'),
    path('internal/segments/', create_segment, name='create-segment'),
    path('internal/segments/expired/', expired_segments, name='expired-segments'),
    path('internal/segments/<uuid:pk>/', delete_segment, name='delete-segment'),
    path('internal/storage-files/', register_storage_file, name='register-storage-file'),
    path('internal/storage-files/bulk/', bulk_register_storage_files, name='bulk-register-storage-files'),
    # Internal: purge endpoints
    path('internal/storage/policies/', storage_policies_all, name='storage-policies-all'),
    path('internal/storage/stats/', storage_stats, name='storage-stats'),
    path('internal/storage/purge-segments/', purge_expired_segments, name='purge-segments'),
    path('internal/storage/purge-files/', purge_old_storage_files, name='purge-files'),
    path('internal/storage/purge-events/', purge_old_events, name='purge-events'),
    path('internal/storage/tier-move-segments/', tier_move_segments, name='tier-move-segments'),
    path('internal/storage/tier-confirm-move/', tier_confirm_move, name='tier-confirm-move'),
]
