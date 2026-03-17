"""Internal API endpoints for service-to-service communication (no tenant auth)."""
import json
import os

from django.http import JsonResponse
from django.views import View

from .models import RegionOfInterest
from apps.cameras.models import Camera, DetectionMask

INTERNAL_SECRET = os.getenv('INTERNAL_SECRET', 'internal-secret-change-me')
MEDIAMTX_INTERNAL = os.getenv('MEDIAMTX_HLS_INTERNAL', 'rtsp://mediamtx:8554')


class RoiSyncView(View):
    """Returns all active cameras with their ROIs for frame-grabber startup sync.

    Authentication: INTERNAL_SECRET query param checked against env var.
    Only accessible from within the Docker network (no public route).
    """

    def get(self, request):
        secret = request.GET.get('secret', '')
        if not secret or secret != INTERNAL_SECRET:
            return JsonResponse({'error': 'Forbidden'}, status=403)

        cameras = (
            Camera.objects.filter(rois__active=True)
            .distinct()
            .select_related('tenant')
        )

        result = []
        for camera in cameras:
            rois = list(
                RegionOfInterest.objects.filter(camera=camera, active=True)
                .values('id', 'name', 'polygon', 'ia_type', 'ia_types', 'config')
            )
            masks = list(
                DetectionMask.objects.filter(camera=camera, active=True)
                .values('id', 'polygon')
            )
            stream_url = f'rtsp://mediamtx:8554/live/{camera.tenant_id}/{camera.id}'
            result.append({
                'camera_id': str(camera.id),
                'tenant_id': str(camera.tenant_id),
                'stream_url': stream_url,
                'roi_list': rois,
                'masks': masks,
            })

        return JsonResponse({'cameras': result})
