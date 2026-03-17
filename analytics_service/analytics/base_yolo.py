"""Base YOLO — compartilhada por intrusion_detection, people_count e vehicle_count."""
import asyncio
import logging
import os
import time
from abc import abstractmethod
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from analytics.base import AnalyticsPlugin, AnalyticsResult, FrameMetadata, ROIConfig

logger = logging.getLogger(__name__)


def point_in_polygon(
    cx: float,
    cy: float,
    polygon_points: list[list[float]],
    frame_w: int,
    frame_h: int,
) -> bool:
    """Retorna True se ponto normalizado (cx, cy) está dentro do polígono.

    Args:
        cx: Coordenada X normalizada (0.0–1.0).
        cy: Coordenada Y normalizada (0.0–1.0).
        polygon_points: [[x, y], ...] normalizados.
        frame_w: Largura do frame em pixels.
        frame_h: Altura do frame em pixels.
    """
    if len(polygon_points) < 3:
        return False
    poly = np.array(
        [[p[0] * frame_w, p[1] * frame_h] for p in polygon_points],
        dtype=np.float32,
    )
    result = cv2.pointPolygonTest(poly, (cx * frame_w, cy * frame_h), measureDist=False)
    return result >= 0


def centroids_in_roi(
    detections: list[dict[str, Any]],
    roi: ROIConfig,
    frame_w: int,
    frame_h: int,
) -> list[dict[str, Any]]:
    """Filtra detecções cujo centroid está dentro da ROI.

    Args:
        detections: Lista de dicts com chave 'xyxy' em pixels.
        roi: ROI com polygon_points normalizados.
        frame_w: Largura do frame.
        frame_h: Altura do frame.

    Returns:
        Subset de detections dentro da ROI.
    """
    inside = []
    for det in detections:
        x1, y1, x2, y2 = det["xyxy"]
        cx = (x1 + x2) / 2 / frame_w
        cy = (y1 + y2) / 2 / frame_h
        if point_in_polygon(cx, cy, roi.polygon_points, frame_w, frame_h):
            inside.append(det)
    return inside


class YOLOPlugin(AnalyticsPlugin):
    """Base para plugins que rodam YOLOv8n sobre ROIs.

    Subclasses precisam implementar apenas `process_frame`.
    O modelo é carregado uma vez em `initialize()` e reutilizado.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._snapshots = Path(os.environ.get("SNAPSHOTS_PATH", "/recordings/snapshots"))

    def _save_snapshot(self, frame: np.ndarray, camera_id: int, prefix: str = "det") -> str:
        """Salva frame como JPEG no diretório de snapshots. Retorna o caminho absoluto."""
        try:
            self._snapshots.mkdir(parents=True, exist_ok=True)
            ts = int(time.time() * 1000)
            filename = f"cam{camera_id}_{prefix}_{ts}.jpg"
            path = self._snapshots / filename
            cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            return str(path)
        except Exception as exc:
            logger.warning("_save_snapshot: falha ao salvar frame: %s", exc)
            return ""

    async def initialize(self, config: dict[str, Any]) -> None:
        """Carrega o modelo YOLO em executor para não bloquear o loop."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model, config)
        logger.info("%s inicializado", self.__class__.__name__)

    def _load_model(self, config: dict[str, Any]) -> None:
        from ultralytics import YOLO
        model_path = config.get("model", "yolov8n.pt")
        self._model = YOLO(model_path)
        self._imgsz = int(os.environ.get("YOLO_IMGSZ", "640"))
        self._conf  = float(os.environ.get("YOLO_CONF", "0.30"))
        logger.info(
            "%s: modelo '%s' carregado — imgsz=%d conf=%.2f",
            self.__class__.__name__, model_path, self._imgsz, self._conf,
        )

    async def shutdown(self) -> None:
        logger.info("%s encerrado", self.__class__.__name__)

    def _run_inference(
        self,
        frame: np.ndarray,
        class_ids: set[int],
    ) -> list[dict[str, Any]]:
        """Executa YOLOv8 e retorna detecções filtradas por classe.

        Args:
            frame: BGR numpy array.
            class_ids: Conjunto de IDs de classe COCO a manter.

        Returns:
            Lista de dicts com 'xyxy', 'class_id', 'confidence'.
        """
        results = self._model(frame, verbose=False, imgsz=self._imgsz, conf=self._conf)[0]
        detections = []
        for box in results.boxes:
            if int(box.cls) not in class_ids:
                continue
            detections.append({
                "xyxy": box.xyxy[0].tolist(),
                "class_id": int(box.cls),
                "confidence": round(float(box.conf), 3),
            })
        return detections

    @abstractmethod
    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Implementado por cada subclasse."""
