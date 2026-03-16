"""Testes para serviços de storage quota."""
import os
import tempfile
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.recordings.models import Clip, RecordingSegment
from apps.recordings.services import check_storage_quota, get_tenant_storage_bytes
from tests.factories import CameraFactory, TenantFactory, UserFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestGetTenantStorageBytes:
    """Testes do cálculo de uso de storage por tenant."""

    def setup_method(self):
        self.tenant = TenantFactory()
        self.camera = CameraFactory(tenant=self.tenant)

    def _make_segment(self, file_path: str) -> RecordingSegment:
        now = timezone.now()
        return RecordingSegment.objects.create(
            camera=self.camera,
            tenant=self.tenant,
            start_time=now - timedelta(seconds=60),
            end_time=now,
            duration_seconds=60,
            file_path=file_path,
        )

    def _make_clip(self, file_path: str) -> Clip:
        now = timezone.now()
        return Clip.objects.create(
            tenant=self.tenant,
            camera=self.camera,
            start_time=now - timedelta(seconds=10),
            end_time=now + timedelta(seconds=20),
            status=Clip.Status.READY,
            file_path=file_path,
        )

    def test_returns_zero_when_no_files(self):
        """Retorna 0 quando não há segmentos nem clips."""
        total = get_tenant_storage_bytes(self.tenant.id)
        assert total == 0

    def test_sums_segment_file_sizes(self):
        """Soma o tamanho de arquivos de segmentos existentes."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 1000)
            path1 = f.name

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 2000)
            path2 = f.name

        try:
            self._make_segment(path1)
            self._make_segment(path2)

            total = get_tenant_storage_bytes(self.tenant.id)
            assert total == 3000
        finally:
            os.unlink(path1)
            os.unlink(path2)

    def test_sums_clip_file_sizes(self):
        """Soma o tamanho de arquivos de clips existentes."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 500)
            path = f.name

        try:
            self._make_clip(path)

            total = get_tenant_storage_bytes(self.tenant.id)
            assert total == 500
        finally:
            os.unlink(path)

    def test_ignores_missing_files(self):
        """Ignora entradas de DB cujo arquivo não existe no disco."""
        self._make_segment("/nonexistent/segment.mp4")
        self._make_clip("/nonexistent/clip.mp4")

        total = get_tenant_storage_bytes(self.tenant.id)
        assert total == 0

    def test_ignores_other_tenant_files(self):
        """Não conta arquivos de outros tenants."""
        other_tenant = TenantFactory()
        other_camera = CameraFactory(tenant=other_tenant)
        now = timezone.now()

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 5000)
            other_path = f.name

        try:
            RecordingSegment.objects.create(
                camera=other_camera,
                tenant=other_tenant,
                start_time=now - timedelta(seconds=60),
                end_time=now,
                duration_seconds=60,
                file_path=other_path,
            )

            total = get_tenant_storage_bytes(self.tenant.id)
            assert total == 0
        finally:
            os.unlink(other_path)


@pytest.mark.unit
@pytest.mark.django_db
class TestCheckStorageQuota:
    """Testes do verificador de quota de storage."""

    def setup_method(self):
        self.tenant = TenantFactory()

    @patch("apps.recordings.services.get_tenant_storage_bytes", return_value=0)
    def test_returns_dict_with_expected_keys(self, mock_bytes):
        """Retorna dicionário com used_bytes, quota_bytes e over_quota."""
        result = check_storage_quota(self.tenant.id)

        assert "used_bytes" in result
        assert "quota_bytes" in result
        assert "over_quota" in result
        assert "usage_ratio" in result

    @patch("apps.recordings.services.get_tenant_storage_bytes", return_value=50 * 1024 ** 3)
    def test_under_quota_returns_false(self, mock_bytes):
        """50 GB de 100 GB = não está acima da quota."""
        result = check_storage_quota(self.tenant.id)

        assert result["over_quota"] is False
        assert result["used_bytes"] == 50 * 1024 ** 3

    @patch("apps.recordings.services.get_tenant_storage_bytes", return_value=110 * 1024 ** 3)
    def test_over_quota_returns_true(self, mock_bytes):
        """110 GB de 100 GB = acima da quota."""
        result = check_storage_quota(self.tenant.id)

        assert result["over_quota"] is True

    @patch("apps.recordings.services.get_tenant_storage_bytes", return_value=50 * 1024 ** 3)
    def test_usage_ratio_calculated_correctly(self, mock_bytes):
        """Ratio calculado corretamente."""
        result = check_storage_quota(self.tenant.id)

        expected_ratio = (50 * 1024 ** 3) / (100 * 1024 ** 3)
        assert abs(result["usage_ratio"] - expected_ratio) < 0.001
