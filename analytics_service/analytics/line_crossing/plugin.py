"""Plugin de cruzamento de linha (line_crossing).

Detecta quando um objeto (veículo ou pessoa) cruza uma linha virtual definida
pela ROI. Conta cruzamentos por direção (A→B e B→A).

A ROI pode ser desenhada como:
  - 2 pontos: define diretamente a linha de cruzamento
  - 4 pontos (retângulo/faixa): a linha é o eixo médio entre as bordas opostas

Algoritmo:
  Para cada track, calcula qual lado da linha o centroid está usando o produto
  vetorial. Quando o sinal muda entre frames → cruzamento detectado.

Direções:
  "AB": passou do lado direito para o esquerdo (relativo ao vetor A→B)
  "BA": passou do lado esquerdo para o direito
"""
import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from analytics.base import AnalyticsPlugin, AnalyticsResult, FrameMetadata, ROIConfig

logger = logging.getLogger(__name__)

# Classes COCO detectadas por default: veículos + pessoa
_DEFAULT_CLASS_IDS = {0, 2, 3, 5, 7}  # person, car, motorcycle, bus, truck

_CLASS_NAMES = {0: "person", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# Confiança mínima de detecção
_CONF = float(os.environ.get("LINE_CROSSING_CONF", "0.40"))


def _make_tracker() -> Any:
    import supervision as sv
    TrackerClass = getattr(sv, "ByteTrack", None) or getattr(sv, "ByteTracker")
    return TrackerClass(
        track_activation_threshold=0.30,
        lost_track_buffer=30,
        minimum_matching_threshold=0.70,
        frame_rate=2,
    )


@dataclass
class _CrossingLine:
    """Linha de cruzamento extraída do polígono da ROI."""
    ax: float
    ay: float
    bx: float
    by: float

    def side(self, cx: float, cy: float) -> float:
        """Produto vetorial: > 0 = esquerda (A→B), < 0 = direita."""
        return (self.bx - self.ax) * (cy - self.ay) - (self.by - self.ay) * (cx - self.ax)


def _extract_line(roi: ROIConfig) -> _CrossingLine | None:
    """Extrai a linha de cruzamento do polígono da ROI.

    - 2 pontos: usa os 2 diretamente
    - 4 pontos (faixa): usa o eixo médio entre borda 01 e borda 23
    - outros: usa primeiro e último ponto
    """
    pts = roi.polygon_points
    if len(pts) < 2:
        return None

    if len(pts) == 2:
        return _CrossingLine(pts[0][0], pts[0][1], pts[1][0], pts[1][1])

    if len(pts) == 4:
        # Borda 0-1 e borda 2-3 são as "bordas longas" da faixa
        ax = (pts[0][0] + pts[1][0]) / 2
        ay = (pts[0][1] + pts[1][1]) / 2
        bx = (pts[2][0] + pts[3][0]) / 2
        by = (pts[2][1] + pts[3][1]) / 2
        return _CrossingLine(ax, ay, bx, by)

    # Polígono livre: primeiro ao último ponto
    return _CrossingLine(pts[0][0], pts[0][1], pts[-1][0], pts[-1][1])


class LineCrossingPlugin(AnalyticsPlugin):
    """Detecta cruzamentos de linha virtual via YOLOv8n + ByteTrack."""

    name    = "line_crossing"
    version = "1.0.0"
    roi_type = "line_crossing"

    def __init__(self) -> None:
        self._model: Any = None
        self._trackers:  dict[int, Any]                   = {}  # camera_id → tracker
        # camera_id → roi_id → track_id → last_side (float)
        self._sides: dict[int, dict[int, dict[int, float]]] = {}

    async def initialize(self, config: dict[str, Any]) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model, config)
        logger.info("LineCrossingPlugin inicializado")

    def _load_model(self, config: dict[str, Any]) -> None:
        from ultralytics import YOLO
        model_path = config.get("model", "yolov8n.pt")
        self._model = YOLO(model_path)
        dummy = np.zeros((320, 320, 3), dtype=np.uint8)
        self._model(dummy, verbose=False)
        logger.info("LineCrossingPlugin: modelo '%s' carregado", model_path)

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        if not rois:
            return []
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._process, frame, metadata, rois
            )
        except Exception:
            logger.exception("LineCrossingPlugin: erro inesperado")
            return []

    async def shutdown(self) -> None:
        logger.info("LineCrossingPlugin encerrado")

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _process(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        import supervision as sv

        h, w = frame.shape[:2]
        camera_id = metadata.camera_id

        # Detecta + rastreia
        class_ids = set()
        for roi in rois:
            class_ids |= set(roi.config.get("class_ids", list(_DEFAULT_CLASS_IDS)))

        results_yolo = self._model(frame, conf=_CONF, verbose=False)[0]
        detections   = sv.Detections.from_ultralytics(results_yolo)

        if detections.class_id is not None:
            mask       = np.isin(detections.class_id, list(class_ids))
            detections = detections[mask]

        tracker = self._get_tracker(camera_id)
        tracked = tracker.update_with_detections(detections)

        if tracked.tracker_id is None or len(tracked) == 0:
            return []

        roi_sides = self._sides.setdefault(camera_id, {})
        results: list[AnalyticsResult] = []

        for roi in rois:
            line = _extract_line(roi)
            if line is None:
                continue

            track_sides = roi_sides.setdefault(roi.id, {})

            for i in range(len(tracked)):
                if tracked.tracker_id[i] is None:
                    continue

                tid      = int(tracked.tracker_id[i])
                x1, y1, x2, y2 = tracked.xyxy[i].tolist()
                cx = (x1 + x2) / 2 / w
                cy = (y1 + y2) / 2 / h

                curr_side = line.side(cx, cy)
                prev_side = track_sides.get(tid)

                # Atualiza lado atual (ignora pontos exatamente na linha)
                if abs(curr_side) > 1e-6:
                    track_sides[tid] = curr_side

                # Cruzamento = mudança de sinal
                if prev_side is None or (prev_side * curr_side >= 0):
                    continue

                direction = "AB" if prev_side > 0 else "BA"
                class_id  = int(tracked.class_id[i]) if tracked.class_id is not None else -1
                obj_class = _CLASS_NAMES.get(class_id, "unknown")

                logger.info(
                    "Cruzamento câmera=%d roi='%s' track=%d classe=%s direção=%s",
                    camera_id, roi.name, tid, obj_class, direction,
                )

                results.append(AnalyticsResult(
                    plugin=self.name,
                    camera_id=camera_id,
                    tenant_id=metadata.tenant_id,
                    event_type="analytics.line_crossing.detected",
                    payload={
                        "roi_id":    roi.id,
                        "roi_name":  roi.name,
                        "track_id":  tid,
                        "direction": direction,
                        "class":     obj_class,
                        "timestamp": metadata.timestamp.isoformat(),
                    },
                ))

        # Limpa tracks que sumiram para evitar crescimento infinito
        active_ids = {int(tid) for tid in tracked.tracker_id if tid is not None}
        for roi_id, track_sides in roi_sides.items():
            for tid in list(track_sides):
                if tid not in active_ids:
                    del track_sides[tid]

        return results

    def _get_tracker(self, camera_id: int) -> Any:
        if camera_id not in self._trackers:
            self._trackers[camera_id] = _make_tracker()
        return self._trackers[camera_id]
