"""Plugin de detecção de intrusão em zona virtual.

Detecta pessoas (e opcionalmente veículos) dentro de polígonos ROI configurados.
Dispara um evento por ROI por frame onde há ao menos uma detecção dentro da zona.

Classes COCO detectadas por default: person (0).
Configurável via ROI.config["class_ids"] para incluir veículos.
"""
import asyncio
import logging
from typing import Any

import numpy as np

from analytics.base import AnalyticsResult, FrameMetadata, ROIConfig
from analytics.base_yolo import YOLOPlugin, centroids_in_roi

logger = logging.getLogger(__name__)

# Classe "person" no dataset COCO
_DEFAULT_CLASS_IDS = {0}


class IntrusionDetectionPlugin(YOLOPlugin):
    """Detecta intrusão de pessoas em zonas virtuais via YOLOv8n."""

    name = "intrusion_detection"
    version = "1.0.0"
    roi_type = "intrusion"

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Retorna um AnalyticsResult por ROI onde há intrusão.

        A detecção é stateless: cada frame é avaliado de forma independente.
        Para evitar flood de eventos, o rate limiting deve ser feito pelo consumidor.
        """
        if not rois:
            return []
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, self._process, frame, metadata, rois
            )
            return results
        except Exception:
            logger.exception("IntrusionDetectionPlugin: erro inesperado")
            return []

    def _process(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        h, w = frame.shape[:2]

        # Determina classes a detectar (pode variar por ROI, usa o maior conjunto)
        all_class_ids: set[int] = set()
        for roi in rois:
            ids = set(roi.config.get("class_ids", list(_DEFAULT_CLASS_IDS)))
            all_class_ids |= ids

        detections = self._run_inference(frame, all_class_ids)
        if not detections:
            return []

        results = []
        for roi in rois:
            roi_class_ids = set(roi.config.get("class_ids", list(_DEFAULT_CLASS_IDS)))
            roi_dets = [d for d in detections if d["class_id"] in roi_class_ids]
            inside = centroids_in_roi(roi_dets, roi, w, h)
            if not inside:
                continue

            frame_path = self._save_snapshot(
                frame, metadata.camera_id, f"intrusion_roi{roi.id}"
            )
            results.append(AnalyticsResult(
                plugin=self.name,
                camera_id=metadata.camera_id,
                tenant_id=metadata.tenant_id,
                event_type="analytics.intrusion.detected",
                payload={
                    "roi_id": roi.id,
                    "roi_name": roi.name,
                    "detection_count": len(inside),
                    "frame_path": frame_path,
                    "detections": [
                        {
                            "class_id": d["class_id"],
                            "confidence": d["confidence"],
                            "bbox": [round(v) for v in d["xyxy"]],
                        }
                        for d in inside
                    ],
                    "timestamp": metadata.timestamp.isoformat(),
                },
            ))

        return results
