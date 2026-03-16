"""Testes para a task periódica cameras.health_check_all."""
from unittest.mock import call, patch

import pytest

from apps.cameras.tasks import health_check_all_cameras_task
from tests.factories import CameraFactory, TenantFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestHealthCheckAllCamerasTask:
    """Testes da task health_check_all_cameras_task."""

    @patch("apps.cameras.tasks.check_online_status")
    def test_dispatches_subtask_per_camera(self, mock_check):
        """Uma sub-task é despachada para cada câmera existente."""
        tenant = TenantFactory()
        cam1 = CameraFactory(tenant=tenant)
        cam2 = CameraFactory(tenant=tenant)

        result = health_check_all_cameras_task()

        assert result["cameras_dispatched"] == 2
        mock_check.delay.assert_any_call(cam1.id)
        mock_check.delay.assert_any_call(cam2.id)

    @patch("apps.cameras.tasks.check_online_status")
    def test_no_cameras_returns_zero(self, mock_check):
        """Com nenhuma câmera cadastrada retorna zero sem erros."""
        result = health_check_all_cameras_task()

        assert result["cameras_dispatched"] == 0
        mock_check.delay.assert_not_called()

    @patch("apps.cameras.tasks.check_online_status")
    def test_dispatches_correct_count(self, mock_check):
        """Resultado reflete o número exato de câmeras despachadas."""
        TenantFactory()  # tenant sem câmeras não conta
        tenant = TenantFactory()
        CameraFactory.create_batch(5, tenant=tenant)

        result = health_check_all_cameras_task()

        assert result["cameras_dispatched"] == 5
        assert mock_check.delay.call_count == 5


@pytest.mark.unit
@pytest.mark.django_db
class TestCheckStorageQuotaTask:
    """Testes da task periódica recordings.check_storage_quota."""

    def test_runs_without_tenants(self):
        """Task não falha quando não há tenants."""
        from apps.recordings.tasks import check_storage_quota_task

        result = check_storage_quota_task()

        assert isinstance(result, dict)
        assert len(result) == 0

    def test_returns_result_per_tenant(self):
        """Retorna dict com entrada por tenant."""
        from apps.recordings.tasks import check_storage_quota_task

        tenant = TenantFactory()

        result = check_storage_quota_task()

        assert tenant.id in result
        assert "used_bytes" in result[tenant.id]
        assert "quota_bytes" in result[tenant.id]
        assert "over_quota" in result[tenant.id]

    @patch("apps.recordings.tasks.logger")
    def test_logs_error_when_critical(self, mock_logger):
        """Loga ERROR quando tenant está em uso crítico (≥95%)."""
        from apps.recordings.tasks import check_storage_quota_task

        tenant = TenantFactory()

        with patch("apps.recordings.services.check_storage_quota") as mock_quota:
            mock_quota.return_value = {
                "used_bytes": 97 * 1024 ** 3,
                "quota_bytes": 100 * 1024 ** 3,
                "usage_ratio": 0.97,
                "over_quota": False,
            }
            check_storage_quota_task()

        mock_logger.error.assert_called()


@pytest.mark.unit
@pytest.mark.django_db
class TestCleanupRecordingsTask:
    """Testes da task periódica recordings.cleanup_task."""

    def test_runs_without_cameras(self):
        """Task não falha quando não há câmeras."""
        from apps.recordings.tasks import cleanup_recordings_task

        result = cleanup_recordings_task()

        assert isinstance(result, dict)
        assert result["cameras_processed"] == 0
        assert result["segments_deleted"] == 0

    @patch("apps.recordings.services.cleanup_old_recordings")
    def test_delegates_to_service(self, mock_cleanup):
        """Task delega para o service cleanup_old_recordings."""
        from apps.recordings.tasks import cleanup_recordings_task

        mock_cleanup.return_value = {
            "cameras_processed": 3,
            "segments_deleted": 12,
            "errors": 0,
        }

        result = cleanup_recordings_task()

        mock_cleanup.assert_called_once()
        assert result["segments_deleted"] == 12
