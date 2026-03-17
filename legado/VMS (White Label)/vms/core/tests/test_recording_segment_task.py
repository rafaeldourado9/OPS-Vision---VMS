from unittest.mock import MagicMock, patch

import pytest
from apps.recordings.tasks import process_recording_segment_task

from apps.recordings.models import RecordingSegment
from tests.factories import CameraFactory


@pytest.mark.django_db
class TestProcessRecordingSegmentTask:
    """Testes para a task de indexação de segmentos de gravação."""

    @patch("apps.recordings.tasks.subprocess.run")
    def test_process_recording_segment_success(self, mock_run):
        """Task processa segmento corretamente e cria o modelo no banco."""
        camera = CameraFactory()
        # Mock do retorno do ffprobe
        # Duração de 10.0 segundos, timestamp absoluto de "2026-03-14T10:00:10.000000Z"
        mock_stdout = b'{"format": {"duration": "10.0", "tags": {"creation_time": "2026-03-14T10:00:10.000000Z"}}}'
        mock_process = MagicMock()
        mock_process.stdout = mock_stdout
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # O webhook vai mandar o "path" que no nosso sistema vira o tenant/camera
        # E o file path real gerado pelo MediaMTX
        mediamtx_path = f"tenant-{camera.tenant_id}/cam-{camera.id}"
        file_path = f"/recordings/tenant-{camera.tenant_id}/cam-{camera.id}/2026-03-14_10-00-00.mp4"

        # Roda a task síncrona para o teste
        result = process_recording_segment_task(mediamtx_path, file_path)

        assert result is True

        # Valida banco
        segment = RecordingSegment.objects.get(camera=camera)
        assert segment.tenant == camera.tenant
        assert segment.file_path == file_path
        assert segment.duration_seconds == 10

        # O end_time deve ser o creation_time (10:00:10)
        assert segment.end_time.isoformat() == "2026-03-14T10:00:10+00:00"

        # O start_time deve ser 10:00:10.0 - 10.0 = 10:00:00.0
        assert segment.start_time.isoformat() == "2026-03-14T10:00:00+00:00"

    @patch("apps.recordings.tasks.subprocess.run")
    def test_process_recording_segment_ffprobe_fails(self, mock_run):
        """Task falha se o ffprobe não conseguir ler o arquivo."""
        camera = CameraFactory()
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_run.return_value = mock_process

        with pytest.raises(Exception, match="Failed to probe video file"):
            process_recording_segment_task(f"tenant-{camera.tenant_id}/cam-{camera.id}", "/fake/path.mp4")

    def test_process_recording_segment_camera_not_found(self):
        """Task ignora com erro se a câmera não for encontrada pelo path."""
        with pytest.raises(ValueError, match="Invalid mediamtx path format"):
            process_recording_segment_task("invalid-path", "/fake.mp4")

        with pytest.raises(Exception, match="Camera not found"):
            process_recording_segment_task("tenant-99/cam-99", "/fake.mp4")
