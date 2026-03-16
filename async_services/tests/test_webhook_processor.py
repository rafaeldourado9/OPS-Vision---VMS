"""Testes para process_mediamtx_event — despacho direto para Celery."""
from unittest.mock import MagicMock, patch

import pytest

from services.webhook_processor import process_mediamtx_event


class TestProcessMediaMTXEvent:
    """Garante que eventos MediaMTX disparam a task Celery correta."""

    @patch("services.webhook_processor._get_celery_app")
    def test_record_segment_sends_process_segment_task(self, mock_get_app):
        """record_segment → recordings.process_segment."""
        mock_app = MagicMock()
        mock_get_app.return_value = mock_app

        process_mediamtx_event("record_segment", {
            "path": "tenant-1/cam-2",
            "file_path": "/recordings/tenant-1/cam-2/2026-03-14.mp4",
        })

        mock_app.send_task.assert_called_once_with(
            "recordings.process_segment",
            args=["tenant-1/cam-2", "/recordings/tenant-1/cam-2/2026-03-14.mp4"],
        )

    @patch("services.webhook_processor._get_celery_app")
    def test_on_ready_sends_set_online_true(self, mock_get_app):
        """on_ready (câmera conectou) → cameras.set_online(camera_id, True)."""
        mock_app = MagicMock()
        mock_get_app.return_value = mock_app

        process_mediamtx_event("on_ready", {
            "path": "tenant-3/cam-7",
            "source_type": "rtspSource",
            "source_id": "abc",
        })

        mock_app.send_task.assert_called_once_with(
            "cameras.set_online",
            args=[7, True],
        )

    @patch("services.webhook_processor._get_celery_app")
    def test_on_not_ready_sends_set_online_false(self, mock_get_app):
        """on_not_ready (câmera desconectou) → cameras.set_online(camera_id, False)."""
        mock_app = MagicMock()
        mock_get_app.return_value = mock_app

        process_mediamtx_event("on_not_ready", {
            "path": "tenant-3/cam-7",
            "source_type": "rtspSource",
            "source_id": "abc",
        })

        mock_app.send_task.assert_called_once_with(
            "cameras.set_online",
            args=[7, False],
        )

    @patch("services.webhook_processor._publish_to_rabbitmq")
    def test_on_read_publishes_to_rabbitmq(self, mock_publish):
        """on_read não tem ação Celery — publicado no event bus."""
        process_mediamtx_event("on_read", {
            "path": "tenant-1/cam-1",
            "reader_type": "webrtcSession",
            "reader_id": "x",
        })

        mock_publish.assert_called_once_with(
            "stream.viewer_joined",
            {"path": "tenant-1/cam-1", "reader_type": "webrtcSession", "reader_id": "x"},
        )

    @patch("services.webhook_processor._get_celery_app")
    def test_invalid_path_does_not_raise(self, mock_get_app):
        """Path malformado não propaga exceção."""
        mock_app = MagicMock()
        mock_get_app.return_value = mock_app

        process_mediamtx_event("on_ready", {"path": "invalid-path"})

        mock_app.send_task.assert_not_called()
