"""Plugin de contagem de veículos em zonas virtuais.

Conta veículos (car, motorcycle, bus, truck) dentro de cada ROI configurada.
Publica um evento por ROI quando count > 0.
Stateless — sem tracking, cada frame é avaliado independentemente.
"""
import asyncio
import logging

import numpy as np

from analytics.base import AnalyticsResult, FrameMetadata, ROIConfig
from analytics.base_yolo import YOLOPlugin, centroids_in_roi

logger = logging.getLogger(__name__)

# Classes COCO de veículos: car=2, motorcycle=3, bus=5, truck=7
_VEHICLE_CLASS_IDS = {2, 3, 5, 7}

_CLASS_NAMES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


class VehicleCountPlugin(YOLOPlugin):
    """Conta veículos em ROIs via YOLOv8n."""

    name = "vehicle_count"
    version = "1.0.0"
    roi_type = "vehicle_traffic"

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Retorna um AnalyticsResult por ROI onde count > 0."""
        if not rois:
            return []
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._process, frame, metadata, rois
            )
        except Exception:
            logger.exception("VehicleCountPlugin: erro inesperado")
            return []

    def _process(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        h, w = frame.shape[:2]

        # Permite filtrar classes via config da ROI (ex: apenas carros)
        results = []
        for roi in rois:
            class_ids = set(roi.config.get("class_ids", list(_VEHICLE_CLASS_IDS)))
            detections = self._run_inference(frame, class_ids)
            inside = centroids_in_roi(detections, roi, w, h)
            count = len(inside)

            threshold = int(roi.config.get("min_count", 0))
            if count <= threshold:
                continue

            # Contagem por tipo de veículo
            by_class: dict[str, int] = {}
            for det in inside:
                label = _CLASS_NAMES.get(det["class_id"], str(det["class_id"]))
                by_class[label] = by_class.get(label, 0) + 1

            logger.info(
                "Contagem câmera=%d roi='%s' count=%d %s",
                metadata.camera_id, roi.name, count, by_class,
            )
            results.append(AnalyticsResult(
                plugin=self.name,
                camera_id=metadata.camera_id,
                tenant_id=metadata.tenant_id,
                event_type="analytics.vehicle.count",
                payload={
                    "roi_id": roi.id,
                    "roi_name": roi.name,
                    "count": count,
                    "by_class": by_class,
                    "timestamp": metadata.timestamp.isoformat(),
                },
            ))

        return results
