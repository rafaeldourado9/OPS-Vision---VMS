from django.urls import path
from .views import (
    DashboardStatsView,
    DashboardDetectionsByHourView,
    SystemInfoView,
    TrafficByHourView,
    TrafficByDayView,
    EventsByTypeView,
    QueueStatsView,
    CameraHeatmapView,
)

urlpatterns = [
    # Dashboard principal
    path('dashboard/stats/',               DashboardStatsView.as_view()),
    path('dashboard/detections-by-hour/',  DashboardDetectionsByHourView.as_view()),

    # Analytics de tráfego e eventos
    path('analytics/traffic-by-hour/',     TrafficByHourView.as_view()),
    path('analytics/traffic-by-day/',      TrafficByDayView.as_view()),
    path('analytics/events-by-type/',      EventsByTypeView.as_view()),
    path('analytics/queue-stats/',         QueueStatsView.as_view()),

    # Heatmap por câmera
    path('cameras/<uuid:camera_id>/heatmap/', CameraHeatmapView.as_view()),

    # Sistema
    path('system/info/',                   SystemInfoView.as_view()),
]
