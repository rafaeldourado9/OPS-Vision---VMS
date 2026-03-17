"""Plugin de reconhecimento facial (face_recognition).

⚠ LGPD: só processa ROIs do tipo 'facial' se tenant.facial_recognition_enabled=True.
   A verificação é feita no endpoint /internal/rois/ — se desabilitado, nenhuma ROI
   facial é retornada e o plugin não processa nenhum frame.

Pipeline:
  1. InsightFace (buffalo_sc) detecta faces + extrai embedding ArcFace 512-dim
  2. Para cada face: verifica se centroid está dentro de alguma ROI
  3. Envia embedding para Django via ingest
  4. Django compara contra FaceProfiles do tenant e cria FaceDetectionEvent

O matching NÃO ocorre no plugin — não tem acesso ao banco. Django faz o matching.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from analytics.base import AnalyticsPlugin, AnalyticsResult, FrameMetadata, ROIConfig
from analytics.base_yolo import point_in_polygon

logger = logging.getLogger(__name__)

_SNAPSHOTS = Path(os.environ.get("SNAPSHOTS_PATH", "/recordings/snapshots"))
_DET_SIZE  = int(os.environ.get("FACE_DET_SIZE", "320"))   # 320 = rápido, 640 = mais preciso
_MIN_SCORE = float(os.environ.get("FACE_MIN_SCORE", "0.70")) # confiança mínima da detecção


class FaceRecognitionPlugin(AnalyticsPlugin):
    """Detecta rostos e extrai embeddings via InsightFace (buffalo_sc)."""

    name     = "face_recognition"
    version  = "1.0.0"
    roi_type = "facial"

    def __init__(self) -> None:
        self._app: Any = None

    async def initialize(self, config: dict[str, Any]) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model, config)
        _SNAPSHOTS.mkdir(parents=True, exist_ok=True)
        logger.info(
            "FaceRecognitionPlugin v%s — modelo=%s det_size=%d min_score=%.2f",
            self.version,
            config.get("model", "buffalo_sc"),
            _DET_SIZE,
            _MIN_SCORE,
        )

    def _load_model(self, config: dict[str, Any]) -> None:
        from insightface.app import FaceAnalysis
        model = config.get("model", "buffalo_sc")
        self._app = FaceAnalysis(
            name=model,
            providers=["CPUExecutionProvider"],
        )
        self._app.prepare(ctx_id=0, det_size=(_DET_SIZE, _DET_SIZE))
        # Warm-up
        dummy = np.zeros((320, 320, 3), dtype=np.uint8)
        self._app.get(dummy)
        logger.info("InsightFace '%s' carregado e warm-up feito", model)

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
            logger.exception("FaceRecognitionPlugin: erro inesperado")
            return []

    async def shutdown(self) -> None:
        logger.info("FaceRecognitionPlugin encerrado")

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _process(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        fh, fw = frame.shape[:2]

        # Detecta todas as faces no frame
        faces = self._app.get(frame)
        if not faces:
            return []

        results = []
        for roi in rois:
            for face in faces:
                if face.det_score < _MIN_SCORE:
                    continue

                x1, y1, x2, y2 = face.bbox.astype(int)
                cx = (x1 + x2) / 2 / fw
                cy = (y1 + y2) / 2 / fh

                if not point_in_polygon(cx, cy, roi.polygon_points, fw, fh):
                    continue

                # Salva crop do rosto para referência
                frame_path = self._snapshot(frame, x1, y1, x2, y2, metadata.camera_id)

                # normed_embedding: vetor 512-dim já normalizado (L2)
                embedding: list[float] = face.normed_embedding.tolist()

                logger.info(
                    "Rosto detectado: câmera=%d roi='%s' score=%.2f",
                    metadata.camera_id, roi.name, face.det_score,
                )

                results.append(AnalyticsResult(
                    plugin=self.name,
                    camera_id=metadata.camera_id,
                    tenant_id=metadata.tenant_id,
                    event_type="analytics.face.detected",
                    payload={
                        "roi_id":     roi.id,
                        "roi_name":   roi.name,
                        "embedding":  embedding,
                        "det_score":  round(float(face.det_score), 3),
                        "bbox_norm":  [
                            round(x1 / fw, 4), round(y1 / fh, 4),
                            round(x2 / fw, 4), round(y2 / fh, 4),
                        ],
                        "frame_path": frame_path,
                        "timestamp":  metadata.timestamp.isoformat(),
                    },
                ))

        return results

    def _snapshot(
        self, frame: np.ndarray,
        x1: int, y1: int, x2: int, y2: int,
        camera_id: int,
    ) -> str:
        try:
            import time as _t
            ts = int(_t.time() * 1000)
            fh, fw = frame.shape[:2]
            # Padding de 20% ao redor do rosto
            pad_x = int((x2 - x1) * 0.2)
            pad_y = int((y2 - y1) * 0.2)
            crop = frame[
                max(0, y1 - pad_y):min(fh, y2 + pad_y),
                max(0, x1 - pad_x):min(fw, x2 + pad_x),
            ]
            path = _SNAPSHOTS / f"face_cam{camera_id}_{ts}.jpg"
            cv2.imwrite(str(path), crop)
            return str(path)
        except Exception as exc:
            logger.warning("Snapshot de rosto falhou: %s", exc)
            return ""
