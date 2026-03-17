"""Plugin de permanência veicular (vehicle_dwell).

Detecta veículos em ROIs configuradas e registra eventos de permanência
quando um veículo fica estacionado entre MIN_DWELL e MAX_DWELL segundos.

Pipeline:
1. YOLOv8s detecta veículos (car, bus, truck, motorcycle) com conf >= 0.45
2. supervision ByteTrack atribui track_id estável entre frames
3. Para cada track: verifica se centroid está dentro de alguma ROI
4. Ao entrar: registra entered_at + salva snapshot
5. Ao sair ou timeout: calcula dwell_seconds, classifica is_valid, envia resultado

Precisão alvo: 90%+ em cenários de estacionamento.
Modelo padrão: yolov8s.pt (mais preciso que yolov8n, rápido o suficiente a 2 FPS).
"""
import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from analytics.base import AnalyticsPlugin, AnalyticsResult, FrameMetadata, ROIConfig
from analytics.base_yolo import point_in_polygon as _point_in_polygon

logger = logging.getLogger(__name__)

# YOLO class IDs para veículos (COCO)
_VEHICLE_CLASS_IDS = frozenset({2, 3, 5, 7})  # car, motorcycle, bus, truck

# Limites de permanência (segundos)
_MIN_DWELL    = int(os.environ.get("DWELL_MIN_SECONDS", "60"))
_MAX_DWELL    = int(os.environ.get("DWELL_MAX_SECONDS", "240"))

# Timeout antes de considerar que o veículo saiu (segundos)
# A 2 FPS, 15s = 30 frames sem detecção → veículo foi embora
_TRACK_TIMEOUT = int(os.environ.get("DWELL_TRACK_TIMEOUT", "15"))

# Confiança mínima de detecção (0.45 = bom balanço precisão/recall)
_CONF = float(os.environ.get("DWELL_CONF_THRESHOLD", "0.45"))


def _make_tracker() -> Any:
    """Cria tracker compatível com supervision 0.19+ (ByteTrack) e < 0.19 (ByteTracker)."""
    import supervision as sv
    TrackerClass = getattr(sv, "ByteTrack", None) or getattr(sv, "ByteTracker")
    return TrackerClass(
        track_activation_threshold=0.30,  # detecta veículos com boa confiança
        lost_track_buffer=50,             # a 2 FPS = 25s de tolerância a oclusão
        minimum_matching_threshold=0.70,  # IoU mínimo para associar detecção a track
        frame_rate=2,
    )


@dataclass
class _Track:
    """Estado de um veículo sendo rastreado."""
    track_id:   int
    roi_id:     int
    entered_at: datetime
    last_seen:  datetime
    frame_path: str = ""


class VehicleDwellPlugin(AnalyticsPlugin):
    """Detecta permanência veicular em ROIs via YOLOv8s + ByteTrack."""

    name     = "vehicle_dwell"
    version  = "1.1.0"
    roi_type = "vehicle_dwell"

    def __init__(self) -> None:
        self._model:    Any = None
        self._trackers: dict[int, Any]              = {}
        self._active:   dict[int, dict[int, _Track]] = {}
        self._snapshots = Path(os.environ.get("SNAPSHOTS_PATH", "/recordings/snapshots"))

    async def initialize(self, config: dict[str, Any]) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model, config)
        self._snapshots.mkdir(parents=True, exist_ok=True)
        logger.info(
            "VehicleDwellPlugin v%s — modelo=%s conf=%.2f min_dwell=%ds max_dwell=%ds",
            self.version,
            config.get("model", "yolov8s.pt"),
            _CONF,
            _MIN_DWELL,
            _MAX_DWELL,
        )

    def _load_model(self, config: dict[str, Any]) -> None:
        from ultralytics import YOLO
        # yolov8s.pt: ~22MB, ~90% mAP em COCO, ~50ms/frame em CPU
        model_path = config.get("model", "yolov8s.pt")
        self._model = YOLO(model_path)
        # Warm-up para evitar latência no primeiro frame real
        dummy = np.zeros((320, 320, 3), dtype=np.uint8)
        self._model(dummy, verbose=False)
        logger.info("YOLO carregado e warm-up feito: %s", model_path)

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        if not rois:
            return []

        camera_id = metadata.camera_id
        now       = metadata.timestamp
        tracker   = self._get_tracker(camera_id)
        active    = self._active.setdefault(camera_id, {})

        loop = asyncio.get_event_loop()
        tracked = await loop.run_in_executor(
            None, self._detect_and_track, frame, tracker
        )

        h, w = frame.shape[:2]
        seen: set[int] = set()
        results: list[AnalyticsResult] = []

        for det in tracked:
            tid = det["track_id"]
            x1, y1, x2, y2 = det["xyxy"]
            cx = (x1 + x2) / 2 / w
            cy = (y1 + y2) / 2 / h
            seen.add(tid)

            matched = next(
                (roi for roi in rois if _point_in_polygon(cx, cy, roi.polygon_points, w, h)),
                None,
            )

            if matched is None:
                # Veículo saiu da ROI
                if tid in active:
                    r = self._close(active, tid, now, camera_id, metadata.tenant_id)
                    if r:
                        results.append(r)
                continue

            if tid not in active:
                active[tid] = _Track(
                    track_id=tid,
                    roi_id=matched.id,
                    entered_at=now,
                    last_seen=now,
                    frame_path=self._snapshot(frame, camera_id, tid),
                )
                logger.info("Veículo track=%d entrou na ROI '%s'", tid, matched.name)
            else:
                trk = active[tid]
                trk.last_seen = now
                if (now - trk.entered_at).total_seconds() > _MAX_DWELL:
                    r = self._close(active, tid, now, camera_id, metadata.tenant_id)
                    if r:
                        results.append(r)

        # Timeout: tracks sem detecção por muito tempo
        for tid in [
            tid for tid, trk in active.items()
            if tid not in seen
            and (now - trk.last_seen).total_seconds() > _TRACK_TIMEOUT
        ]:
            r = self._close(active, tid, active[tid].last_seen, camera_id, metadata.tenant_id)
            if r:
                results.append(r)

        return results

    async def shutdown(self) -> None:
        logger.info("VehicleDwellPlugin encerrado. Tracks ativos: %d câmeras", len(self._active))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_tracker(self, camera_id: int) -> Any:
        if camera_id not in self._trackers:
            self._trackers[camera_id] = _make_tracker()
        return self._trackers[camera_id]

    def _detect_and_track(self, frame: np.ndarray, tracker: Any) -> list[dict[str, Any]]:
        import supervision as sv

        results    = self._model(frame, conf=_CONF, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(results)

        # Filtra apenas veículos
        if detections.class_id is not None:
            mask       = np.isin(detections.class_id, list(_VEHICLE_CLASS_IDS))
            detections = detections[mask]

        # Atualiza tracker SEMPRE (mesmo sem detecções, para aging de tracks perdidos)
        tracked = tracker.update_with_detections(detections)

        if tracked.tracker_id is None:
            return []

        return [
            {
                "track_id": int(tracked.tracker_id[i]),
                "xyxy":     tracked.xyxy[i].tolist(),
                "class_id": int(tracked.class_id[i]) if tracked.class_id is not None else -1,
            }
            for i in range(len(tracked))
            if tracked.tracker_id[i] is not None
        ]

    def _close(
        self,
        active: dict[int, _Track],
        tid: int,
        exited_at: datetime,
        camera_id: int,
        tenant_id: int,
    ) -> AnalyticsResult | None:
        trk = active.pop(tid, None)
        if trk is None:
            return None

        dwell = int((exited_at - trk.entered_at).total_seconds())
        valid = _MIN_DWELL <= dwell <= _MAX_DWELL

        logger.info(
            "Veículo track=%d câmera=%d dwell=%ds válido=%s",
            tid, camera_id, dwell, valid,
        )

        return AnalyticsResult(
            plugin=self.name,
            camera_id=camera_id,
            tenant_id=tenant_id,
            event_type="analytics.vehicle.dwell",
            payload={
                "track_id":      tid,
                "roi_id":        trk.roi_id,
                "entered_at":    trk.entered_at.isoformat(),
                "exited_at":     exited_at.isoformat(),
                "dwell_seconds": dwell,
                "frame_path":    trk.frame_path,
                "is_valid":      valid,
            },
        )

    def _snapshot(self, frame: np.ndarray, camera_id: int, tid: int) -> str:
        try:
            path = self._snapshots / f"cam{camera_id}_track{tid}.jpg"
            cv2.imwrite(str(path), frame)
            return str(path)
        except Exception as exc:
            logger.warning("Snapshot falhou: %s", exc)
            return ""
