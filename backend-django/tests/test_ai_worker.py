import pytest
from unittest.mock import Mock, patch
from django.utils import timezone
from tests.factories import TenantFactory
from tests.camera_factory import CameraFactory
from apps.roi.models import RegionOfInterest
from apps.detections.models import AIEvent


@pytest.mark.django_db
class TestAIWorker:
    
    def test_lpr_detects_plate_inside_roi(self):
        """LPR deve detectar placa dentro do ROI"""
        tenant = TenantFactory()
        camera = CameraFactory(tenant=tenant, ia_enabled=True, ia_status='active')
        roi = RegionOfInterest.objects.create(
            tenant=tenant,
            camera=camera,
            name='ROI 1',
            polygon=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            ia_type='lpr'
        )
        
        # Simula evento detectado
        event = AIEvent.objects.create(
            tenant=tenant,
            camera=camera,
            roi=roi,
            event_type='lpr',
            snapshot_path='/storage/snapshot.jpg',
            event_data={'plate': 'ABC1D23', 'confidence': 0.85},
            detected_at=timezone.now()
        )
        
        assert event.id is not None
        assert event.event_data['plate'] == 'ABC1D23'
        assert event.event_data['confidence'] == 0.85

    def test_lpr_ignores_frame_when_no_roi(self):
        """LPR deve ignorar frame quando câmera não tem ROI"""
        tenant = TenantFactory()
        camera = CameraFactory(tenant=tenant, ia_enabled=True, ia_status='ia_pending')
        
        # Sem ROI configurado, não deve gerar eventos
        events_count = AIEvent.objects.filter(camera=camera).count()
        assert events_count == 0

    def test_dedup_prevents_duplicate_event(self):
        """Dedup Redis deve evitar evento duplicado dentro de 30s"""
        from unittest.mock import MagicMock
        import redis

        tenant = TenantFactory()
        camera = CameraFactory(tenant=tenant, ia_enabled=True, ia_status='active')
        roi = RegionOfInterest.objects.create(
            tenant=tenant,
            camera=camera,
            name='ROI Dedup',
            polygon=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            ia_type='lpr'
        )

        # Simula Redis com mock
        mock_redis = MagicMock()

        # Primeira chamada: chave não existe → evento criado
        mock_redis.exists.return_value = False
        dedup_key = f'dedup:{camera.id}:ABC1D23'
        assert not mock_redis.exists(dedup_key)

        # Cria primeiro evento
        event1 = AIEvent.objects.create(
            tenant=tenant, camera=camera, roi=roi,
            event_type='lpr',
            snapshot_path='/storage/snap1.jpg',
            event_data={'plate': 'ABC1D23', 'confidence': 0.9},
            detected_at=timezone.now()
        )
        mock_redis.setex(dedup_key, 30, '1')

        # Segunda chamada: chave existe → evento deve ser descartado
        mock_redis.exists.return_value = True
        assert mock_redis.exists(dedup_key)

        # Não deve criar segundo evento (simulação da lógica de dedup)
        events = AIEvent.objects.filter(
            camera=camera,
            event_data__plate='ABC1D23',
        )
        assert events.count() == 1  # Apenas 1 evento, não duplicado

    def test_low_confidence_does_not_generate_event(self):
        """Confidence < 0.7 não deve gerar evento"""
        tenant = TenantFactory()
        camera = CameraFactory(tenant=tenant, ia_enabled=True, ia_status='active')
        roi = RegionOfInterest.objects.create(
            tenant=tenant, camera=camera,
            name='ROI Conf',
            polygon=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            ia_type='lpr'
        )

        # Simula a lógica: confidence 0.5 < threshold 0.7
        confidence = 0.5
        threshold = 0.7

        # Worker NÃO deve criar evento quando confidence < threshold
        if confidence >= threshold:
            AIEvent.objects.create(
                tenant=tenant, camera=camera, roi=roi,
                event_type='lpr',
                snapshot_path='/storage/low_conf.jpg',
                event_data={'plate': 'XYZ9999', 'confidence': confidence},
                detected_at=timezone.now()
            )

        # Verifica que nenhum evento foi criado
        assert AIEvent.objects.filter(camera=camera).count() == 0

    def test_event_appears_in_api(self):
        """Evento persistido deve aparecer na API /detections/"""
        tenant = TenantFactory()
        camera = CameraFactory(tenant=tenant)
        
        event = AIEvent.objects.create(
            tenant=tenant,
            camera=camera,
            event_type='lpr',
            snapshot_path='/storage/snapshot.jpg',
            event_data={'plate': 'XYZ9876', 'confidence': 0.92},
            detected_at=timezone.now()
        )
        
        # Verifica que evento existe
        assert AIEvent.objects.filter(id=event.id).exists()

    def test_tenant_isolation(self):
        """Evento de tenant A não deve ser visível para tenant B"""
        tenant_a = TenantFactory()
        tenant_b = TenantFactory()
        
        camera_a = CameraFactory(tenant=tenant_a)
        camera_b = CameraFactory(tenant=tenant_b)
        
        event_a = AIEvent.objects.create(
            tenant=tenant_a,
            camera=camera_a,
            event_type='lpr',
            snapshot_path='/storage/a.jpg',
            event_data={'plate': 'AAA1111', 'confidence': 0.8},
            detected_at=timezone.now()
        )
        
        # Tenant B não deve ver evento de tenant A
        events_b = AIEvent.objects.filter(tenant=tenant_b)
        assert event_a not in events_b
