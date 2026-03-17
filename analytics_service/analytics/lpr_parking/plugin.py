"""Plugin de leitura de placas server-side (LPR).

Pipeline melhorado para câmeras com baixa resolução ou placas distantes:
  1. Recorta o bounding box da ROI do frame
  2. Faz upscale do crop (padrão 2x) → mais pixels para o detector
  3. Aplica CLAHE → melhora contraste em condições adversas de luz
  4. plate_detector.pt detecta regiões de placa no crop processado
  5. fast-plate-ocr lê o texto de cada placa detectada

Upscale configurável via LPR_UPSCALE_FACTOR (default: 2).
Desabilitar pré-processamento: LPR_PREPROCESS=false.
"""
import asyncio
import logging
import os
import time
from typing import Any

import cv2
import numpy as np

from analytics.base import AnalyticsPlugin, AnalyticsResult, FrameMetadata, ROIConfig

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH  = os.environ.get("PLATE_DETECTOR_MODEL", "/models/plate_detector.pt")
_MIN_PLATE_CHARS     = 6
_CONF_THRESHOLD      = float(os.environ.get("LPR_CONF_THRESHOLD", "0.35"))  # mais baixo com upscale
_DEDUP_TTL           = int(os.environ.get("LPR_DEDUP_TTL_SECONDS", "60"))
_UPSCALE_FACTOR      = float(os.environ.get("LPR_UPSCALE_FACTOR", "2.0"))
_PREPROCESS          = os.environ.get("LPR_PREPROCESS", "true").lower() != "false"
# Tamanho mínimo do crop da ROI para valer a pena processar (pixels)
_MIN_ROI_PX          = int(os.environ.get("LPR_MIN_ROI_PX", "64"))


def _roi_bbox(roi: ROIConfig, w: int, h: int) -> tuple[int, int, int, int]:
    """Retorna bounding box da ROI em pixels (x1, y1, x2, y2)."""
    xs = [p[0] * w for p in roi.polygon_points]
    ys = [p[1] * h for p in roi.polygon_points]
    return (
        max(0, int(min(xs))),
        max(0, int(min(ys))),
        min(w, int(max(xs))),
        min(h, int(max(ys))),
    )


def _preprocess(crop: np.ndarray, scale: float) -> np.ndarray:
    """Upscale + CLAHE para maximizar detecção em placas pequenas/escuras."""
    if scale != 1.0:
        new_w = int(crop.shape[1] * scale)
        new_h = int(crop.shape[0] * scale)
        crop = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    # CLAHE no canal L do espaço LAB — melhora contraste sem saturar cores
    lab   = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


class LPRParkingPlugin(AnalyticsPlugin):
    """Detecta e lê placas em ROIs com upscale + CLAHE para baixa resolução."""

    name    = "lpr_parking"
    version = "2.0.0"
    roi_type = "lpr"

    def __init__(self) -> None:
        self._plate_model: Any = None
        self._ocr:         Any = None
        self._dedup: dict[tuple[int, str], float] = {}

    async def initialize(self, config: dict[str, Any]) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_models, config)
        logger.info(
            "LPRParkingPlugin v%s — upscale=%.1fx preprocess=%s conf=%.2f",
            self.version, _UPSCALE_FACTOR, _PREPROCESS, _CONF_THRESHOLD,
        )

    def _load_models(self, config: dict[str, Any]) -> None:
        from ultralytics import YOLO
        from fast_plate_ocr import LicensePlateRecognizer

        model_path = config.get("plate_model", _DEFAULT_MODEL_PATH)
        self._plate_model = YOLO(model_path)

        # Warm-up com imagem pequena
        dummy = np.zeros((128, 256, 3), dtype=np.uint8)
        self._plate_model(dummy, verbose=False)

        ocr_model = config.get("ocr_model", "global-plates-mobile-vit-v2-model")
        self._ocr = LicensePlateRecognizer(ocr_model)
        logger.info("plate_detector='%s' ocr='%s'", model_path, ocr_model)

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
            return await loop.run_in_executor(None, self._process, frame, metadata, rois)
        except Exception:
            logger.exception("LPRParkingPlugin: erro inesperado")
            return []

    async def shutdown(self) -> None:
        logger.info("LPRParkingPlugin encerrado")

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _process(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        fh, fw = frame.shape[:2]
        results = []

        for roi in rois:
            # 1. Recorta bounding box da ROI
            x1, y1, x2, y2 = _roi_bbox(roi, fw, fh)
            if (x2 - x1) < _MIN_ROI_PX or (y2 - y1) < _MIN_ROI_PX:
                logger.debug("ROI '%s' muito pequena (%dx%d), ignorando", roi.name, x2-x1, y2-y1)
                continue

            roi_crop = frame[y1:y2, x1:x2].copy()

            # 2. Pré-processa: upscale + CLAHE
            if _PREPROCESS:
                processed = _preprocess(roi_crop, _UPSCALE_FACTOR)
            else:
                processed = roi_crop

            # 3. Detecta placas no crop processado
            detections = self._detect_plates(processed)
            if not detections:
                continue

            logger.debug(
                "ROI '%s': %d placa(s) detectada(s) no crop %dx%d→%dx%d",
                roi.name, len(detections),
                roi_crop.shape[1], roi_crop.shape[0],
                processed.shape[1], processed.shape[0],
            )

            # 4. OCR em cada crop de placa
            plate_crops = [self._crop(processed, d["xyxy"]) for d in detections]
            plate_crops = [c for c in plate_crops if c.size > 0]
            if not plate_crops:
                continue

            plates = self._read_plates(plate_crops)

            for plate_text in plates:
                if not self._is_valid(plate_text):
                    continue
                if self._is_duplicate(metadata.camera_id, plate_text):
                    logger.debug("Dedup: %s câmera=%d", plate_text, metadata.camera_id)
                    continue

                self._mark_seen(metadata.camera_id, plate_text)
                logger.info(
                    "Placa lida: %s | câmera=%d roi='%s' conf=%.2f",
                    plate_text, metadata.camera_id, roi.name,
                    max(d["confidence"] for d in detections),
                )
                results.append(AnalyticsResult(
                    plugin=self.name,
                    camera_id=metadata.camera_id,
                    tenant_id=metadata.tenant_id,
                    event_type="analytics.lpr.detection",
                    payload={
                        "plate":     plate_text,
                        "roi_id":    roi.id,
                        "roi_name":  roi.name,
                        "timestamp": metadata.timestamp.isoformat(),
                    },
                ))

        return results

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _detect_plates(self, img: np.ndarray) -> list[dict[str, Any]]:
        results = self._plate_model(img, conf=_CONF_THRESHOLD, verbose=False)[0]
        return [
            {"xyxy": box.xyxy[0].tolist(), "confidence": round(float(box.conf), 3)}
            for box in results.boxes
        ]

    def _read_plates(self, crops: list[np.ndarray]) -> list[str]:
        try:
            texts = self._ocr.run(crops)
            return [t.replace("_", "").strip() for t in texts if t]
        except Exception as exc:
            logger.error("OCR erro: %s", exc)
            return []

    @staticmethod
    def _crop(img: np.ndarray, xyxy: list[float]) -> np.ndarray:
        x1, y1, x2, y2 = map(int, xyxy)
        h, w = img.shape[:2]
        return img[max(0,y1):min(h,y2), max(0,x1):min(w,x2)]

    @staticmethod
    def _is_valid(plate: str) -> bool:
        return len(plate) >= _MIN_PLATE_CHARS and plate.isalnum()

    def _is_duplicate(self, camera_id: int, plate: str) -> bool:
        return time.monotonic() < self._dedup.get((camera_id, plate), 0)

    def _mark_seen(self, camera_id: int, plate: str) -> None:
        self._dedup[(camera_id, plate)] = time.monotonic() + _DEDUP_TTL
        if len(self._dedup) > 1000:
            now = time.monotonic()
            self._dedup = {k: v for k, v in self._dedup.items() if v > now}
