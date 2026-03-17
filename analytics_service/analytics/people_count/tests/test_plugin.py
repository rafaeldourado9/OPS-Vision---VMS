"""Testes do PeopleCountPlugin."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

import numpy as np
import pytest

from analytics.base import FrameMetadata, ROIConfig
from analytics.people_count.plugin import PeopleCountPlugin


@pytest.fixture
def plugin():
    p = PeopleCountPlugin()
    p._model = MagicMock()
    return p


@pytest.fixture
def meta():
    return FrameMetadata(
        camera_id=2,
        tenant_id=1,
        timestamp=datetime.now(tz=timezone.utc),
        stream_url="rtsp://localhost/tenant-1/cam-2",
    )


@pytest.fixture
def roi():
    return ROIConfig(
        id=10,
        name="Saguão",
        ia_type="human_traffic",
        polygon_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
    )


def _make_person_box(cx, cy, frame_w=640, frame_h=480):
    x1, y1 = (cx - 0.04) * frame_w, (cy - 0.08) * frame_h
    x2, y2 = (cx + 0.04) * frame_w, (cy + 0.08) * frame_h
    box = MagicMock()
    box.cls = MagicMock()
    box.cls.__int__ = lambda s: 0  # person
    box.conf = MagicMock()
    box.conf.__float__ = lambda s: 0.88
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


def test_sem_pessoas_retorna_vazio(plugin, meta, roi):
    _mock_model(plugin, [])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi])) == []


def test_uma_pessoa_dentro_da_roi(plugin, meta, roi):
    _mock_model(plugin, [_make_person_box(0.5, 0.5)])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi]))

    assert len(results) == 1
    r = results[0]
    assert r.plugin == "people_count"
    assert r.event_type == "analytics.people.count"
    assert r.payload["count"] == 1
    assert r.payload["roi_id"] == roi.id
    assert r.camera_id == meta.camera_id


def test_tres_pessoas_conta_correto(plugin, meta, roi):
    boxes = [_make_person_box(0.2, 0.5), _make_person_box(0.5, 0.5), _make_person_box(0.8, 0.5)]
    _mock_model(plugin, boxes)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi]))

    assert len(results) == 1
    assert results[0].payload["count"] == 3


def test_pessoa_fora_da_roi_ignorada(plugin, meta):
    roi_pequena = ROIConfig(
        id=11,
        name="Canto",
        ia_type="human_traffic",
        polygon_points=[[0.0, 0.0], [0.2, 0.0], [0.2, 0.2], [0.0, 0.2]],
    )
    _mock_model(plugin, [_make_person_box(0.8, 0.8)])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi_pequena]))
    assert results == []


def test_threshold_min_count(plugin, meta):
    """Com min_count=2, apenas 1 pessoa não deve disparar evento."""
    roi_threshold = ROIConfig(
        id=12,
        name="Controlado",
        ia_type="human_traffic",
        polygon_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        config={"min_count": 2},
    )
    _mock_model(plugin, [_make_person_box(0.5, 0.5)])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = asyncio.run(plugin.process_frame(frame, meta, [roi_threshold]))
    assert results == []


def test_excecao_nao_propaga(plugin, meta, roi):
    plugin._model.side_effect = RuntimeError("OOM")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert asyncio.run(plugin.process_frame(frame, meta, [roi])) == []
