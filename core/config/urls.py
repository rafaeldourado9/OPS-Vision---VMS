"""URL configuration."""
from django.contrib import admin
from django.urls import include, path
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


class AuthAnonRateThrottle(AnonRateThrottle):
    """Throttle anônimo para endpoints de autenticação (5/min)."""

    scope = "auth_anon"


class AuthUserRateThrottle(UserRateThrottle):
    """Throttle autenticado para endpoints de autenticação (60/min)."""

    scope = "auth_user"


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """Token obtain com rate limit restritivo: 5/min anônimo, 60/min auth."""

    throttle_classes = [AuthAnonRateThrottle, AuthUserRateThrottle]


class ThrottledTokenRefreshView(TokenRefreshView):
    """Token refresh com rate limit restritivo: 5/min anônimo, 60/min auth."""

    throttle_classes = [AuthAnonRateThrottle, AuthUserRateThrottle]


urlpatterns = [
    path("admin/", admin.site.urls),
    # Health check (sem auth)
    path("api/v1/health/", include("apps.health.urls")),
    # Auth
    path("api/v1/auth/token/", ThrottledTokenObtainPairView.as_view(), name="token_obtain"),
    path("api/v1/auth/token/refresh/", ThrottledTokenRefreshView.as_view(), name="token_refresh"),
    # Apps
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.cameras.urls")),
    path("api/v1/", include("apps.events.urls")),
    path("api/v1/", include("apps.recordings.urls")),
    path("api/v1/", include("apps.agents.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.analytics.urls")),
]
