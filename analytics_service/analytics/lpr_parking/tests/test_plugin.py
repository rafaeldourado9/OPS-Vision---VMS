"""Testes do LPRParkingPlugin."""
import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from analytics.base import FrameMetadata, ROIConfig
from analytics.lpr_parking.plugin import LPRParkingPlugin


@pytest.fixture
def plugin():
    p = LPRParkingPlugin()
    p._plate_model = MagicMock()
    p._ocr = MagicMock()
    return p


@pytest.fixture
def meta():
    return FrameMetadata(
        camera_id=5,
        tenant_id=1,
        timestamp=datetime.now(tz=timezone.utc),
        stream_url="rtsp://localhost/tenant-1/cam-5",
    )


@pytest.fixture
def roi():
    return ROIConfig(
        id=30,
        name="Entrada",
        ia_type="lpr",
        polygon_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
    )


def _make_plate_box(cx=0.5, cy=0.5, frame_w=640, frame_h=480, conf=0.85):
    x1, y1 = (cx - 0.05) * frame_w, (cy - 0.02) * frame_h
    x2, y2 = (cx + 0.05) * frame_w, (cy + 0.02) * frame_h
    box = MagicMock()
    box.cls = MagicMock()
    box.cls.__int__ = lambda s: 0
    box.conf = MagicMock()
    box.conf.__float__ = lambda s: conf
    box.xyxy = [MagicMock()]
    box.xyxy[0].tolist.return_value = [x1, y1, x2, y2]
    return box


def _mock_detector(plugin, boxes):
    result = MagicMock()
    result.boxes = boxes
    plugin._plate_model.return_value = [result]


def _mock_ocr(plugin, texts):
    plugin._ocr.run.return_value = texts


# ── Testes ────────────────────────────────────────────────────────────────────

def test_sem_roi_retorna_vazio(plugin, meta):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [])) == []


def test_sem_deteccoes_retorna_vazio(plugin, meta, roi):
    _mock_detector(plugin, [])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi])) == []


def test_placa_valida_retorna_resultado(plugin, meta, roi):
    _mock_detector(plugin, [_make_plate_box(0.5, 0.5)])
    _mock_ocr(plugin, ["ABC1D23"])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi]))

    assert len(results) == 1
    r = results[0]
    assert r.plugin == "lpr_parking"
    assert r.event_type == "analytics.lpr.detection"
    assert r.payload["plate"] == "ABC1D23"
    assert r.payload["roi_id"] == roi.id
    assert r.camera_id == meta.camera_id


def test_placa_curta_ignorada(plugin, meta, roi):
    """Texto com menos de 6 chars não é uma placa válida."""
    _mock_detector(plugin, [_make_plate_box()])
    _mock_ocr(plugin, ["AB1"])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi])) == []


def test_placa_com_caracteres_especiais_ignorada(plugin, meta, roi):
    """Texto com underscores ou espaços após strip não é alfanumérico."""
    _mock_detector(plugin, [_make_plate_box()])
    _mock_ocr(plugin, ["ABC-1D23"])  # hífen → não isalnum
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi])) == []


def test_underscore_removido_automaticamente(plugin, meta, roi):
    """fast-plate-ocr pode retornar underscores como padding — devem ser removidos."""
    _mock_detector(plugin, [_make_plate_box()])
    _mock_ocr(plugin, ["ABC1D23__"])  # underscores removidos → "ABC1D23" válido
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi]))
    assert len(results) == 1
    assert results[0].payload["plate"] == "ABC1D23"


def test_placa_fora_da_roi_ignorada(plugin, meta):
    roi_pequena = ROIConfig(
        id=31,
        name="Vaga",
        ia_type="lpr",
        polygon_points=[[0.0, 0.0], [0.2, 0.0], [0.2, 0.2], [0.0, 0.2]],
    )
    _mock_detector(plugin, [_make_plate_box(cx=0.9, cy=0.9)])
    _mock_ocr(plugin, ["XYZ9W12"])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi_pequena])) == []


def test_dedup_segunda_leitura_ignorada(plugin, meta, roi):
    """Segunda leitura da mesma placa dentro do TTL deve ser ignorada."""
    _mock_detector(plugin, [_make_plate_box()])
    _mock_ocr(plugin, ["ABC1D23"])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    results1 = asyncio.run(plugin.process_frame(frame, meta, [roi]))
    results2 = asyncio.run(plugin.process_frame(frame, meta, [roi]))

    assert len(results1) == 1
    assert len(results2) == 0  # dedup bloqueou


def test_dedup_placa_diferente_nao_bloqueada(plugin, meta, roi):
    """Placas diferentes não interferem no dedup uma da outra."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    _mock_detector(plugin, [_make_plate_box()])

    _mock_ocr(plugin, ["ABC1D23"])
    r1 = asyncio.run(plugin.process_frame(frame, meta, [roi]))

    _mock_ocr(plugin, ["XYZ9W12"])
    r2 = asyncio.run(plugin.process_frame(frame, meta, [roi]))

    assert len(r1) == 1
    assert len(r2) == 1


def test_dedup_expira_apos_ttl(plugin, meta, roi):
    """Após TTL expirado a mesma placa deve ser aceita novamente."""
    plugin._dedup[(meta.camera_id, "ABC1D23")] = time.monotonic() - 1  # já expirou

    _mock_detector(plugin, [_make_plate_box()])
    _mock_ocr(plugin, ["ABC1D23"])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi]))
    assert len(results) == 1


def test_excecao_nao_propaga(plugin, meta, roi):
    plugin._plate_model.side_effect = RuntimeError("modelo corrompido")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi])) == []


def test_ocr_exception_nao_propaga(plugin, meta, roi):
    _mock_detector(plugin, [_make_plate_box()])
    plugin._ocr.run.side_effect = RuntimeError("OCR crash")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi])) == []
