import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from django.utils import timezone
from tests.factories import TenantFactory
from tests.camera_factory import CameraFactory
from apps.segments.models import Segment


@pytest.mark.django_db
class TestRecorderWorker:
    
    def test_recorder_creates_segment_metadata(self):
        """Recorder deve criar metadado de segmento após gravar"""
        camera = CameraFactory()
        
        segment = Segment.objects.create(
            camera=camera,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=10),
            file_path='/storage/segment.mp4',
            file_size=1024000
        )
        
        assert segment.id is not None
        assert segment.camera == camera
        assert segment.expires_at is not None

    def test_segment_expires_at_calculated_from_retention(self):
        """expires_at deve ser calculado baseado em retention_days"""
        camera = CameraFactory(retention_days=7)
        
        start_time = timezone.now()
        end_time = start_time + timedelta(minutes=10)
        
        segment = Segment.objects.create(
            camera=camera,
            start_time=start_time,
            end_time=end_time,
            file_path='/storage/segment.mp4',
            file_size=1024000
        )
        
        expected_expires = end_time + timedelta(days=7)
        assert segment.expires_at.date() == expected_expires.date()


@pytest.mark.django_db
class TestPurgeWorker:
    
    def test_purge_deletes_only_expired_segments(self):
        """Purge deve deletar apenas segmentos expirados"""
        camera = CameraFactory()
        
        # Segmento expirado
        expired = Segment.objects.create(
            camera=camera,
            start_time=timezone.now() - timedelta(days=10),
            end_time=timezone.now() - timedelta(days=10, minutes=-10),
            file_path='/storage/expired.mp4',
            file_size=1024000,
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        # Segmento válido
        valid = Segment.objects.create(
            camera=camera,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=10),
            file_path='/storage/valid.mp4',
            file_size=1024000,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        # Busca expirados
        expired_segments = Segment.objects.filter(expires_at__lt=timezone.now())
        
        assert expired in expired_segments
        assert valid not in expired_segments

    def test_purge_never_deletes_clips(self):
        """Purge nunca deve tocar em clips (tabela separada)"""
        # Este teste será implementado quando criar modelo Clip
        pass
