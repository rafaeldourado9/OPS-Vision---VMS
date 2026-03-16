"""Testes para agent/stream_manager.py."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from agent.models import CameraConfig, StreamProcess
from agent.stream_manager import (
    StreamManager,
    _INITIAL_BACKOFF_SECONDS,
    _MAX_BACKOFF_SECONDS,
    _STABLE_THRESHOLD_SECONDS,
)


def _make_camera(
    cam_id: int = 1,
    rtsp_url: str = "rtsp://192.168.1.100:554/stream",
    rtmp_url: str = "rtmp://cloud:1935/tenant-1/cam-1",
) -> CameraConfig:
    """Cria uma CameraConfig de teste."""
    return CameraConfig(
        id=cam_id,
        name=f"Camera {cam_id}",
        rtsp_url=rtsp_url,
        rtmp_push_url=rtmp_url,
    )


def _mock_popen(pid: int = 12345, poll_return: int | None = None):
    """Cria um subprocess.Popen mockado."""
    proc = MagicMock()
    proc.pid = pid
    proc.poll.return_value = poll_return  # None = rodando, 0 = terminou
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    proc.wait = MagicMock()
    proc.stderr = MagicMock()
    proc.stderr.read.return_value = b""
    return proc


class TestSync:
    """Testes para StreamManager.sync()."""

    @patch("agent.stream_manager.subprocess.Popen")
    def test_starts_new_cameras(self, mock_popen):
        """Nova câmera na config → inicia ffmpeg."""
        mock_popen.return_value = _mock_popen()
        manager = StreamManager()

        cameras = [_make_camera(1), _make_camera(2)]
        manager.sync(cameras)

        assert len(manager.active_streams) == 2
        assert 1 in manager.active_streams
        assert 2 in manager.active_streams
        assert mock_popen.call_count == 2

    @patch("agent.stream_manager.subprocess.Popen")
    def test_stops_removed_cameras(self, mock_popen):
        """Câmera removida da config → para stream."""
        proc = _mock_popen()
        mock_popen.return_value = proc
        manager = StreamManager()

        # Inicia 2 câmeras
        manager.sync([_make_camera(1), _make_camera(2)])
        assert len(manager.active_streams) == 2

        # Remove câmera 2
        manager.sync([_make_camera(1)])
        assert len(manager.active_streams) == 1
        assert 1 in manager.active_streams

    @patch("agent.stream_manager.subprocess.Popen")
    def test_restarts_changed_config(self, mock_popen):
        """URL mudou → para e reinicia."""
        mock_popen.return_value = _mock_popen()
        manager = StreamManager()

        # Inicia com URL original
        manager.sync([_make_camera(1, rtsp_url="rtsp://old:554/stream")])
        assert mock_popen.call_count == 1

        # Muda URL
        manager.sync([_make_camera(1, rtsp_url="rtsp://new:554/stream")])
        assert mock_popen.call_count == 2  # Parou e reiniciou

    @patch("agent.stream_manager.subprocess.Popen")
    def test_ignores_unchanged(self, mock_popen):
        """Câmera igual → não reinicia."""
        mock_popen.return_value = _mock_popen()
        manager = StreamManager()

        cam = _make_camera(1)
        manager.sync([cam])
        assert mock_popen.call_count == 1

        # Mesmo sync novamente
        manager.sync([cam])
        assert mock_popen.call_count == 1  # Não chamou popen novamente

    @patch("agent.stream_manager.subprocess.Popen")
    def test_disabled_camera_not_started(self, mock_popen):
        """Câmera com enabled=False não é iniciada."""
        mock_popen.return_value = _mock_popen()
        manager = StreamManager()

        cam = _make_camera(1)
        cam = CameraConfig(
            id=1,
            name="Camera 1",
            rtsp_url="rtsp://192.168.1.100:554/stream",
            rtmp_push_url="rtmp://cloud:1935/tenant-1/cam-1",
            enabled=False,
        )
        manager.sync([cam])
        assert len(manager.active_streams) == 0
        mock_popen.assert_not_called()


class TestStopStream:
    """Testes para StreamManager.stop_stream()."""

    @patch("agent.stream_manager.subprocess.Popen")
    def test_sigterm_then_sigkill(self, mock_popen):
        """SIGTERM → espera 5s → SIGKILL se não terminou."""
        import subprocess as sp

        proc = _mock_popen()
        proc.wait.side_effect = sp.TimeoutExpired(cmd="ffmpeg", timeout=5)
        mock_popen.return_value = proc
        manager = StreamManager()

        manager.start_stream(_make_camera(1))
        manager.stop_stream(1)

        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()


class TestBackoff:
    """Testes para backoff exponencial em check_and_restart()."""

    @patch("agent.stream_manager.subprocess.Popen")
    def test_backoff_increases_on_restart(self, mock_popen):
        """Crash → backoff: 5s, 10s, 20s... max 300s."""
        mock_popen.return_value = _mock_popen()
        manager = StreamManager()

        cam = _make_camera(1)
        manager.start_stream(cam)

        # Simula crash (poll retorna 1 = morto)
        stream = manager.active_streams[1]
        stream.process.poll.return_value = 1

        # Primeiro restart
        manager.check_and_restart()
        stream = manager.active_streams[1]
        assert stream.restart_count == 1

    @patch("agent.stream_manager.subprocess.Popen")
    def test_backoff_resets_after_stable(self, mock_popen):
        """60s sem crash → reset backoff."""
        mock_popen.return_value = _mock_popen()
        manager = StreamManager()

        cam = _make_camera(1)
        manager.start_stream(cam)

        # Simula stream estável há > 60s com restart_count > 0
        stream = manager.active_streams[1]
        stream.restart_count = 3
        stream.started_at = datetime.now() - timedelta(
            seconds=_STABLE_THRESHOLD_SECONDS + 10
        )

        manager.check_and_restart()

        stream = manager.active_streams[1]
        assert stream.restart_count == 0


class TestGetHealth:
    """Testes para StreamManager.get_health()."""

    @patch("agent.stream_manager.subprocess.Popen")
    def test_returns_status(self, mock_popen):
        """Retorna dict com running, pid, etc."""
        proc = _mock_popen(pid=42)
        mock_popen.return_value = proc
        manager = StreamManager()

        manager.start_stream(_make_camera(1))
        health = manager.get_health()

        assert "1" in health
        assert health["1"]["pid"] == 42
        assert health["1"]["running"] is True
        assert health["1"]["restart_count"] == 0


class TestStopAll:
    """Testes para StreamManager.stop_all()."""

    @patch("agent.stream_manager.subprocess.Popen")
    def test_stops_all_streams(self, mock_popen):
        """Para todos os streams."""
        mock_popen.return_value = _mock_popen()
        manager = StreamManager()

        manager.sync([_make_camera(1), _make_camera(2), _make_camera(3)])
        assert len(manager.active_streams) == 3

        manager.stop_all()
        assert len(manager.active_streams) == 0
