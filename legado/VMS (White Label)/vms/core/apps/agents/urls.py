"""URLs para agents."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AgentConfigView, AgentHeartbeatView, AgentMeView, AgentViewSet

router = DefaultRouter()
router.register(r"agents", AgentViewSet, basename="agent")

urlpatterns = [
    path("agents/me/", AgentMeView.as_view(), name="agent-me"),
    path("agents/me/config/", AgentConfigView.as_view(), name="agent-config"),
    path("agents/me/heartbeat/", AgentHeartbeatView.as_view(), name="agent-heartbeat"),
    *router.urls,
]
