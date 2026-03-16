from django.urls import path

from .views import (
    CameraPlaybackView,
    CameraStreamView,
    CameraTimelineView,
    ClipDetailView,
    ClipDownloadView,
    ClipListView,
    EventClipCreateView,
    TenantStorageView,
)

app_name = "recordings"

urlpatterns = [
    path("recordings/clips/", ClipListView.as_view(), name="clip-list"),
    path("cameras/<int:camera_id>/timeline/", CameraTimelineView.as_view(), name="camera-timeline"),
    path("cameras/<int:camera_id>/playback/", CameraPlaybackView.as_view(), name="camera-playback"),
    path("cameras/<int:camera_id>/stream/", CameraStreamView.as_view(), name="camera-stream"),
    path("events/<int:event_id>/clip/", EventClipCreateView.as_view(), name="event-clip-create"),
    path("clips/<int:clip_id>/", ClipDetailView.as_view(), name="clip-detail"),
    path("clips/<int:clip_id>/download/", ClipDownloadView.as_view(), name="clip-download"),
    path("recordings/storage/", TenantStorageView.as_view(), name="tenant-storage"),
]
