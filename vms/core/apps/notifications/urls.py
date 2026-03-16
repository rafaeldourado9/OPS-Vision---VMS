"""Rotas para o app de notificações."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import NotificationLogViewSet, NotificationRuleViewSet

router = DefaultRouter()
router.register(r"rules", NotificationRuleViewSet, basename="notification-rules")
router.register(r"logs", NotificationLogViewSet, basename="notification-logs")

app_name = "notifications"

urlpatterns = [
    path("", include(router.urls)),
]
