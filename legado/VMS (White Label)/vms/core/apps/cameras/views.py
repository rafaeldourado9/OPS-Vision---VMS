"""Views para câmeras."""
from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from shared.mediamtx_client import MediaMTXError

from .models import Camera
from .serializers import (
    CameraCreateSerializer,
    CameraSerializer,
    CameraUpdateSerializer,
    LiveStreamSerializer,
    PushConfigSerializer,
)
from .services import (
    CameraCreateInput,
    CameraOfflineError,
    CameraUpdateInput,
    create_camera,
    delete_camera,
    generate_rtmp_push_url,
    get_camera_stream_url,
    update_camera,
)


def _build_path_name_view(camera: Camera) -> str:
    """Constrói nome do path MediaMTX para a câmera."""
    return f"tenant-{camera.tenant_id}/cam-{camera.id}"


class CameraViewSet(viewsets.ModelViewSet):
    """ViewSet para CRUD de câmeras."""

    serializer_class = CameraSerializer
    queryset = Camera.objects.none()

    def get_queryset(self):
        """Retorna apenas câmeras do tenant do usuário."""
        return Camera.objects.filter(
            tenant=self.request.user.tenant
        )

    def create(self, request):
        """Cria uma câmera."""
        serializer = CameraCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            camera = create_camera(CameraCreateInput(
                **serializer.validated_data,
                tenant_id=request.user.tenant_id,
            ))
        except MediaMTXError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            CameraSerializer(camera).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, pk=None):
        """Atualiza uma câmera (PUT)."""
        serializer = CameraUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            camera = update_camera(
                int(pk),
                CameraUpdateInput(**serializer.validated_data),
            )
        except MediaMTXError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(CameraSerializer(camera).data)

    def partial_update(self, request, pk=None):
        """Atualiza uma câmera parcialmente (PATCH)."""
        serializer = CameraUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            camera = update_camera(
                int(pk),
                CameraUpdateInput(**serializer.validated_data),
            )
        except MediaMTXError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(CameraSerializer(camera).data)

    def destroy(self, request, pk=None):
        """Deleta uma câmera."""
        try:
            delete_camera(int(pk))
        except MediaMTXError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="live")
    def live(self, request, pk=None):
        """Retorna URLs de live streaming da câmera.

        Autenticação é feita pelo MediaMTX internamente (authMethod: internal).
        """
        camera = self.get_object()

        path = _build_path_name_view(camera)
        hls_base = getattr(settings, "MEDIAMTX_HLS_BASE_URL", "http://localhost:8888")
        webrtc_base = getattr(settings, "MEDIAMTX_WEBRTC_BASE_URL", "http://localhost:8889")

        data = {
            "camera_id": camera.id,
            "is_online": camera.is_online,
            "hls_url": f"{hls_base}/{path}/index.m3u8",
            "webrtc_url": f"{webrtc_base}/{path}/whep",
            "token": "",
            "expires_at": None,
        }
        return Response(LiveStreamSerializer(data).data)

    @action(detail=True, methods=["get"], url_path="push-config")
    def push_config(self, request, pk=None):
        """Retorna configuração RTMP push para a câmera.

        A resposta contém rtmp_url (server), stream_key e full_url
        para configurar o envio de stream via RTMP push.
        """
        camera = self.get_object()
        data = generate_rtmp_push_url(camera.id, request.user.tenant_id)
        return Response(PushConfigSerializer(data).data)

    @action(detail=True, methods=["get"], url_path="stream-url")
    def stream_url(self, request, pk=None):
        """Retorna URL de streaming da câmera."""
        try:
            url = get_camera_stream_url(int(pk))
            return Response({"url": url})
        except CameraOfflineError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
