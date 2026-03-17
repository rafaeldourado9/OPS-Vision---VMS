"""URLs para analytics."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DwellEventViewSet,
    FaceDetectionEventViewSet,
    FaceProfileViewSet,
    RegionOfInterestViewSet,
    accept_facial_recognition_consent,
    dashboard_events_by_hour,
    dashboard_stats,
    ingest_event,
    internal_rois,
)

router = DefaultRouter()
router.register("analytics/rois", RegionOfInterestViewSet, basename="roi")
router.register("analytics/dwell-events", DwellEventViewSet, basename="dwell-event")
router.register("analytics/face-profiles", FaceProfileViewSet, basename="face-profile")
router.register("analytics/face-events", FaceDetectionEventViewSet, basename="face-event")

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/stats/", dashboard_stats, name="dashboard-stats"),
    path("dashboard/events-by-hour/", dashboard_events_by_hour, name="dashboard-events-by-hour"),
    # LGPD consent
    path("analytics/face-recognition/consent/", accept_facial_recognition_consent, name="face-recognition-consent"),
    # Endpoints internos — autenticados por API key (analytics_service)
    path("analytics/ingest/", ingest_event, name="analytics-ingest"),
    path("analytics/internal/rois/", internal_rois, name="analytics-internal-rois"),
]
