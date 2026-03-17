"""Plugin de contagem de pessoas em zonas virtuais.

Conta pessoas (classe COCO 0) dentro de cada ROI configurada.
Publica um evento por ROI quando o count é maior que zero.
Stateless — sem tracking, cada frame é avaliado independentemente.
"""
import asyncio
import logging
from typing import Any

import numpy as np

from analytics.base import AnalyticsResult, FrameMetadata, ROIConfig
from analytics.base_yolo import YOLOPlugin, centroids_in_roi

logger = logging.getLogger(__name__)

_PERSON_CLASS_IDS = {0}


class PeopleCountPlugin(YOLOPlugin):
    """Conta pessoas em ROIs via YOLOv8n."""

    name = "people_count"
    version = "1.0.0"
    roi_type = "human_traffic"

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
            logger.exception("PeopleCountPlugin: erro inesperado")
            return []

    def _process(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        h, w = frame.shape[:2]
        detections = self._run_inference(frame, _PERSON_CLASS_IDS)

        results = []
        for roi in rois:
            inside = centroids_in_roi(detections, roi, w, h)
            count = len(inside)

            # Respeita threshold configurado na ROI (default: publicar sempre)
            threshold = int(roi.config.get("min_count", 0))
            if count <= threshold:
                continue

            frame_path = self._save_snapshot(
                frame, metadata.camera_id, f"people_roi{roi.id}"
            )
            results.append(AnalyticsResult(
                plugin=self.name,
                camera_id=metadata.camera_id,
                tenant_id=metadata.tenant_id,
                event_type="analytics.people.count",
                payload={
                    "roi_id": roi.id,
                    "roi_name": roi.name,
                    "count": count,
                    "frame_path": frame_path,
                    "timestamp": metadata.timestamp.isoformat(),
                },
            ))

        return results
