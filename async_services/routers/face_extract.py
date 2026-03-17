"""Endpoint de extração de embedding facial para uso interno.

Usado pelo Django quando o operador faz busca por foto
(POST /api/v1/faces/search/).

Autenticação: Analytics API key (mesmo mecanismo do ingest).
"""
import logging
import os
from typing import Any

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["face-extract"])

_SECRET  = os.environ.get("ANALYTICS_SERVICE_API_KEY", "")
_app: Any = None   # InsightFace singleton — carregado lazily


def _get_app():
    global _app
    if _app is None:
        from insightface.app import FaceAnalysis
        _app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
        _app.prepare(ctx_id=0, det_size=(320, 320))
        logger.info("InsightFace carregado para face_extract")
    return _app


@router.post("/faces/extract/")
async def extract_embedding(
    file: UploadFile = File(...),
    authorization: str = "",
) -> JSONResponse:
    """Extrai embedding ArcFace 512-dim de uma foto.

    Autenticação: header Authorization: Analytics <key>

    Retorna:
        {"embedding": [float x 512], "det_score": float}
        ou {"error": "no_face"} se nenhum rosto for detectado.
    """
    from fastapi import Request
    # Valida API key via header direto
    key = authorization.removeprefix("Analytics ").strip()
    if not _SECRET or key != _SECRET:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)

    try:
        import asyncio
        import cv2
        import numpy as np
        contents = await file.read()
        arr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return JSONResponse({"error": "invalid_image"}, status_code=400)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_inference, img)
        return JSONResponse(result)

    except Exception as exc:
        logger.error("face_extract: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


def _run_inference(img) -> dict:
    app = _get_app()
    faces = app.get(img)
    if not faces:
        return {"error": "no_face"}
    # Retorna o rosto com maior área (mais próximo/central)
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    return {
        "embedding": face.normed_embedding.tolist(),
        "det_score": round(float(face.det_score), 3),
    }
