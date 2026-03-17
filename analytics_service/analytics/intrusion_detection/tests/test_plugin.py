"""Testes do IntrusionDetectionPlugin."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from analytics.base import FrameMetadata, ROIConfig
from analytics.intrusion_detection.plugin import IntrusionDetectionPlugin


@pytest.fixture
def plugin():
    p = IntrusionDetectionPlugin()
    p._model = MagicMock()
    return p


@pytest.fixture
def meta():
    return FrameMetadata(
        camera_id=1,
        tenant_id=1,
        timestamp=datetime.now(tz=timezone.utc),
        stream_url="rtsp://localhost/tenant-1/cam-1",
    )


@pytest.fixture
def roi_full():
    """ROI que cobre o frame inteiro."""
    return ROIConfig(
        id=1,
        name="Zona A",
        ia_type="intrusion",
        polygon_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
    )


@pytest.fixture
def roi_small():
    """ROI pequena no canto superior esquerdo."""
    return ROIConfig(
        id=2,
        name="Zona B",
        ia_type="intrusion",
        polygon_points=[[0.0, 0.0], [0.3, 0.0], [0.3, 0.3], [0.0, 0.3]],
    )


def _make_box(cx_norm, cy_norm, frame_w=640, frame_h=480, class_id=0, conf=0.9):
    """Cria mock de box YOLO com centroid na posição normalizada (cx, cy)."""
    x1 = (cx_norm - 0.05) * frame_w
    y1 = (cy_norm - 0.1) * frame_h
    x2 = (cx_norm + 0.05) * frame_w
    y2 = (cy_norm + 0.1) * frame_h
    box = MagicMock()
    box.cls = MagicMock()
    box.cls.__int__ = lambda s: class_id
    box.conf = MagicMock()
    box.conf.__float__ = lambda s: conf
    box.xyxy = [MagicMock()]
    box.xyxy[0].tolist.return_value = [x1, y1, x2, y2]
    return box


def _mock_model(plugin, boxes):
    mock_result = MagicMock()
    mock_result.boxes = boxes
    plugin._model.return_value = [mock_result]


# ── Testes ────────────────────────────────────────────────────────────────────

def test_sem_roi_retorna_vazio(plugin, meta):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = asyncio.run(plugin.process_frame(frame, meta, []))
    assert result == []


def test_sem_deteccoes_retorna_vazio(plugin, meta, roi_full):
    _mock_model(plugin, [])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = asyncio.run(plugin.process_frame(frame, meta, [roi_full]))
    assert result == []


def test_intrusao_dentro_da_roi(plugin, meta, roi_full):
    """Pessoa no centro do frame → dentro da ROI → deve disparar evento."""
    box = _make_box(0.5, 0.5)  # centro exato
    _mock_model(plugin, [box])

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi_full]))

    assert len(results) == 1
    r = results[0]
    assert r.plugin == "intrusion_detection"
    assert r.event_type == "analytics.intrusion.detected"
    assert r.payload["roi_id"] == roi_full.id
    assert r.payload["detection_count"] == 1
    assert r.camera_id == meta.camera_id


def test_deteccao_fora_da_roi_nao_dispara(plugin, meta, roi_small):
    """Pessoa no canto inferior direito → fora da ROI pequena → sem evento."""
    box = _make_box(0.9, 0.9)  # longe da roi_small (0–0.3, 0–0.3)
    _mock_model(plugin, [box])

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi_small]))
    assert results == []


def test_multiplas_rois_independentes(plugin, meta, roi_full, roi_small):
    """Pessoa no centro: dentro de roi_full, fora de roi_small."""
    box = _make_box(0.5, 0.5)
    _mock_model(plugin, [box])

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi_full, roi_small]))

    assert len(results) == 1
    assert results[0].payload["roi_id"] == roi_full.id


def test_multiplas_deteccoes_mesma_roi(plugin, meta, roi_full):
    """Duas pessoas dentro da ROI → detection_count == 2."""
    boxes = [_make_box(0.3, 0.3), _make_box(0.7, 0.7)]
    _mock_model(plugin, boxes)

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi_full]))

    assert len(results) == 1
    assert results[0].payload["detection_count"] == 2


def test_excecao_nao_propaga(plugin, meta, roi_full):
    """Exceção interna não deve propagar — retorna []."""
    plugin._model.side_effect = RuntimeError("GPU error")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi_full]))
    assert results == []


def test_class_ids_configuravel(plugin, meta):
    """ROI configurada com class_ids=[2] (carro) deve ignorar pessoa (0)."""
    roi_carro = ROIConfig(
        id=3,
        name="Entrada",
        ia_type="intrusion",
        polygon_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        config={"class_ids": [2]},
    )
    box_person = _make_box(0.5, 0.5, class_id=0)
    _mock_model(plugin, [box_person])

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi_carro]))
    assert results == []
