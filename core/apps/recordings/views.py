import os

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework.pagination import PageNumberPagination

from apps.cameras.models import Camera
from apps.events.models import Event

from .models import Clip
from .serializers import (
    ClipCreateResponseSerializer,
    ClipCreateSerializer,
    ClipSerializer,
    PlaybackResponseSerializer,
    TimelineSegmentSerializer,
)
from .services import (
    check_storage_quota,
    create_clip,
    create_clip_from_event,
    get_camera_timeline,
    get_playback_segment,
)


class ClipListView(APIView):
    """Lista clips do tenant autenticado com paginação. Aceita POST para criar clip."""

    def get(self, request):
        """Retorna clips paginados, ordenados do mais recente ao mais antigo."""
        queryset = (
            Clip.objects.filter(tenant=request.user.tenant)
            .select_related("camera")
            .order_by("-created_at")
        )

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = ClipSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        """Cria um clip a partir de um intervalo de tempo selecionado."""
        serializer = ClipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        camera = get_object_or_404(
            Camera,
            id=serializer.validated_data["camera_id"],
            tenant=request.user.tenant,
        )

        clip = create_clip(
            camera_id=camera.id,
            tenant_id=request.user.tenant_id,
            start_time=serializer.validated_data["start_time"],
            end_time=serializer.validated_data["end_time"],
        )

        resp = ClipCreateResponseSerializer({"clip_id": clip.id, "status": clip.status})
        return Response(resp.data, status=status.HTTP_201_CREATED)


class TenantStorageView(APIView):
    """Retorna o uso de storage do tenant autenticado."""

    def get(self, request):
        quota_info = check_storage_quota(request.user.tenant_id)
        return Response(quota_info, status=status.HTTP_200_OK)


class CameraTimelineView(APIView):
    """Retorna os segmentos da linha do tempo disponíveis para uma câmera."""

    def get(self, request, camera_id):
        # Enforce tenant isolation
        camera = get_object_or_404(Camera, id=camera_id, tenant=request.user.tenant)

        from_param = request.query_params.get("from")
        to_param = request.query_params.get("to")

        if not from_param or not to_param:
            return Response(
                {"detail": "Parâmetros 'from' e 'to' são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_time = parse_datetime(from_param)
        end_time = parse_datetime(to_param)

        if not start_time or not end_time:
            return Response(
                {"detail": "Formato de data inválido. Use ISO 8601."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        segments = get_camera_timeline(camera.id, start_time, end_time)
        serializer = TimelineSegmentSerializer(segments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CameraPlaybackView(APIView):
    """Localiza o segmento de gravação e retorna metadados para playback."""

    def get(self, request, camera_id):
        camera = get_object_or_404(Camera, id=camera_id, tenant=request.user.tenant)

        timestamp_param = request.query_params.get("timestamp")
        if not timestamp_param:
            return Response(
                {"detail": "Parâmetro 'timestamp' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        timestamp = parse_datetime(timestamp_param)
        if not timestamp:
            return Response(
                {"detail": "Formato de data inválido. Use ISO 8601."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        segment = get_playback_segment(camera.id, timestamp)
        if not segment:
            return Response(
                {"detail": "Nenhuma gravação encontrada para o timestamp informado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        offset_seconds = (timestamp - segment.start_time).total_seconds()

        data = {
            "camera_id": camera.id,
            "segment_start": segment.start_time,
            "segment_end": segment.end_time,
            "offset_seconds": offset_seconds,
            "file_path": segment.file_path,
        }
        serializer = PlaybackResponseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EventClipCreateView(APIView):
    """Cria um clip de vídeo a partir de um evento."""

    def post(self, request, event_id):
        event = get_object_or_404(Event, id=event_id, tenant=request.user.tenant)

        clip = create_clip_from_event(event)

        serializer = ClipCreateResponseSerializer({
            "clip_id": clip.id,
            "status": clip.status,
        })
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ClipDetailView(APIView):
    """Retorna metadados de um clip (usado para polling de status)."""

    def get(self, request, clip_id):
        clip = get_object_or_404(Clip, id=clip_id, tenant=request.user.tenant)
        serializer = ClipSerializer(clip)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ClipDownloadView(APIView):
    """Faz download do arquivo MP4 de um clip pronto."""

    def get(self, request, clip_id):
        clip = get_object_or_404(Clip, id=clip_id, tenant=request.user.tenant)

        if clip.status != Clip.Status.READY:
            return Response(
                {"detail": "Clip ainda não está pronto.", "status": clip.status},
                status=status.HTTP_409_CONFLICT,
            )

        if not clip.file_path or not os.path.exists(clip.file_path):
            return Response(
                {"detail": "Arquivo do clip não encontrado no servidor."},
                status=status.HTTP_404_NOT_FOUND,
            )

        response = FileResponse(
            open(clip.file_path, "rb"),
            content_type="video/mp4",
        )
        response["Content-Disposition"] = f'attachment; filename="clip_{clip.id}.mp4"'
        return response


class CameraStreamView(APIView):
    """Serve o arquivo de vídeo MP4 original com suporte a HTTP 206 Partial Content (Byte-Range).
    
    Isso permite que o player HTML5 faça buffer e seek eficiente sem carregar o arquivo inteiro na memória.
    """

    def get(self, request, camera_id):
        import os
        import re
        from django.http import StreamingHttpResponse, FileResponse

        camera = get_object_or_404(Camera, id=camera_id, tenant=request.user.tenant)

        timestamp_param = request.query_params.get("timestamp")
        if not timestamp_param:
            return Response(
                {"detail": "Parâmetro 'timestamp' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        timestamp = parse_datetime(timestamp_param)
        if not timestamp:
            return Response(
                {"detail": "Formato de data inválido. Use ISO 8601."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        segment = get_playback_segment(camera.id, timestamp)
        
        # O arquivo pode ter sido deletado do disco ou não existir
        if not segment or not os.path.exists(segment.file_path):
            return Response(
                {"detail": "Nenhuma gravação encontrada para o timestamp informado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        file_path = segment.file_path
        file_size = os.path.getsize(file_path)

        range_header = request.META.get("HTTP_RANGE", "").strip()
        range_match = re.search(r"bytes=(\d+)-(\d*)", range_header)

        if range_match:
            first_byte = int(range_match.group(1))
            last_byte = range_match.group(2)
            
            if last_byte:
                last_byte = int(last_byte)
            else:
                last_byte = file_size - 1

            # Validate byte range
            if first_byte >= file_size or last_byte >= file_size or first_byte > last_byte:
                return Response(
                    {"detail": "Range inválido."},
                    status=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                )

            length = last_byte - first_byte + 1

            def file_iterator(file_path, offset, length, chunk_size=8192):
                with open(file_path, "rb") as f:
                    f.seek(offset)
                    remaining = length
                    while remaining > 0:
                        bytes_to_read = min(chunk_size, remaining)
                        data = f.read(bytes_to_read)
                        if not data:
                            break
                        yield data
                        remaining -= len(data)

            response = StreamingHttpResponse(
                file_iterator(file_path, first_byte, length),
                status=status.HTTP_206_PARTIAL_CONTENT,
                content_type="video/mp4",
            )
            response["Content-Length"] = str(length)
            response["Content-Range"] = f"bytes {first_byte}-{last_byte}/{file_size}"
        else:
            # Without range, serve the whole file (typically 60s small mp4 chunks)
            response = FileResponse(open(file_path, "rb"), content_type="video/mp4")
            response["Content-Length"] = str(file_size)

        response["Accept-Ranges"] = "bytes"
        return response
