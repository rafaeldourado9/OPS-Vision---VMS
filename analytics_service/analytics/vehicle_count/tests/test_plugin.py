"""Testes do VehicleCountPlugin."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

import numpy as np
import pytest

from analytics.base import FrameMetadata, ROIConfig
from analytics.vehicle_count.plugin import VehicleCountPlugin


@pytest.fixture
def plugin():
    p = VehicleCountPlugin()
    p._model = MagicMock()
    return p


@pytest.fixture
def meta():
    return FrameMetadata(
        camera_id=3,
        tenant_id=1,
        timestamp=datetime.now(tz=timezone.utc),
        stream_url="rtsp://localhost/tenant-1/cam-3",
    )


@pytest.fixture
def roi():
    return ROIConfig(
        id=20,
        name="Estacionamento",
        ia_type="vehicle_traffic",
        polygon_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
    )


def _make_vehicle_box(cx, cy, class_id=2, frame_w=640, frame_h=480):
    x1, y1 = (cx - 0.06) * frame_w, (cy - 0.05) * frame_h
    x2, y2 = (cx + 0.06) * frame_w, (cy + 0.05) * frame_h
    box = MagicMock()
    box.cls = MagicMock()
    box.cls.__int__ = lambda s: class_id
    box.conf = MagicMock()
    box.conf.__float__ = lambda s: 0.85
    box.xyxy = [MagicMock()]
    box.xyxy[0].tolist.return_value = [x1, y1, x2, y2]
    return box


def _mock_model(plugin, boxes):
    result = MagicMock()
    result.boxes = boxes
    plugin._model.return_value = [result]


# ── Testes ────────────────────────────────────────────────────────────────────

def test_sem_roi_retorna_vazio(plugin, meta):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [])) == []


def test_sem_veiculos_retorna_vazio(plugin, meta, roi):
    _mock_model(plugin, [])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi])) == []


def test_um_carro_dentro_da_roi(plugin, meta, roi):
    _mock_model(plugin, [_make_vehicle_box(0.5, 0.5, class_id=2)])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi]))

    assert len(results) == 1
    r = results[0]
    assert r.plugin == "vehicle_count"
    assert r.event_type == "analytics.vehicle.count"
    assert r.payload["count"] == 1
    assert r.payload["by_class"] == {"car": 1}
    assert r.camera_id == meta.camera_id


def test_tipos_mistos_agrupados_por_classe(plugin, meta, roi):
    """Carro + truck + moto → by_class correto."""
    boxes = [
        _make_vehicle_box(0.2, 0.5, class_id=2),   # car
        _make_vehicle_box(0.5, 0.5, class_id=7),   # truck
        _make_vehicle_box(0.8, 0.5, class_id=3),   # motorcycle
    ]
    _mock_model(plugin, boxes)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi]))

    assert len(results) == 1
    payload = results[0].payload
    assert payload["count"] == 3
    assert payload["by_class"] == {"car": 1, "truck": 1, "motorcycle": 1}


def test_veiculo_fora_da_roi_ignorado(plugin, meta):
    roi_pequena = ROIConfig(
        id=21,
        name="Vaga 1",
        ia_type="vehicle_traffic",
        polygon_points=[[0.0, 0.0], [0.2, 0.0], [0.2, 0.2], [0.0, 0.2]],
    )
    _mock_model(plugin, [_make_vehicle_box(0.9, 0.9)])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi_pequena])) == []


def test_pessoa_nao_e_contada(plugin, meta, roi):
    """Classe person (0) não é veículo e deve ser ignorada."""
    box_pessoa = _make_vehicle_box(0.5, 0.5, class_id=0)
    _mock_model(plugin, [box_pessoa])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi])) == []


def test_class_ids_configuravel(plugin, meta):
    """ROI configurada apenas para bus (5) ignora carros (2)."""
    roi_bus = ROIConfig(
        id=22,
        name="Ponto de ônibus",
        ia_type="vehicle_traffic",
        polygon_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        config={"class_ids": [5]},
    )
    _mock_model(plugin, [_make_vehicle_box(0.5, 0.5, class_id=2)])  # carro
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi_bus])) == []


def test_threshold_min_count(plugin, meta, roi):
    """Com min_count=2, apenas 1 veículo não deve disparar evento."""
    roi_thresh = ROIConfig(
        id=23,
        name="Fila",
        ia_type="vehicle_traffic",
        polygon_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        config={"min_count": 2},
    )
    _mock_model(plugin, [_make_vehicle_box(0.5, 0.5)])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi_thresh])) == []


def test_excecao_nao_propaga(plugin, meta, roi):
    plugin._model.side_effect = RuntimeError("CUDA OOM")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi])) == []
