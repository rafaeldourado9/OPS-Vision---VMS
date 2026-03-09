import pytest
from rest_framework.test import APIClient
from django.utils import timezone
from tests.factories import UserFactory, TenantFactory, LicenseFactory
from apps.cameras.models import Camera


@pytest.mark.django_db
class TestCamerasCRUD:
    
    def setup_method(self):
        self.client = APIClient()
        self.license = LicenseFactory(max_cameras=2)
        self.tenant = TenantFactory(license=self.license)
        self.admin = UserFactory(role='city_admin', tenant=self.tenant, password='pass123')

    def test_create_camera_rtsp_success(self):
        """Criar câmera RTSP com sucesso"""
        self.client.force_authenticate(user=self.admin)
        
        response = self.client.post('/api/v1/cameras/', {
            'name': 'Câmera 1',
            'address': 'Rua A, 123',
            'latitude': -23.5505,
            'longitude': -46.6333,
            'stream_protocol': 'rtsp',
            'stream_url': 'rtsp://camera1.example.com/stream',
            'retention_days': 7
        })
        
        assert response.status_code == 201
        assert response.data['name'] == 'Câmera 1'
        assert response.data['stream_protocol'] == 'rtsp'

    def test_create_camera_rtmp_generates_stream_key(self):
        """Criar câmera RTMP deve gerar stream_key automaticamente"""
        self.client.force_authenticate(user=self.admin)
        
        response = self.client.post('/api/v1/cameras/', {
            'name': 'Câmera RTMP',
            'address': 'Rua B, 456',
            'latitude': -23.5505,
            'longitude': -46.6333,
            'stream_protocol': 'rtmp',
            'retention_days': 15
        })
        
        assert response.status_code == 201
        assert response.data['stream_key'] is not None
        assert len(response.data['stream_key']) == 36  # UUID format

    def test_enable_ia_changes_status_to_pending(self):
        """Habilitar IA deve mudar status para ia_pending"""
        self.client.force_authenticate(user=self.admin)
        
        camera = Camera.objects.create(
            tenant=self.tenant,
            name='Câmera Test',
            address='Test',
            latitude=-23.5505,
            longitude=-46.6333,
            stream_protocol='rtsp',
            stream_url='rtsp://test.com/stream'
        )
        
        response = self.client.patch(f'/api/v1/cameras/{camera.id}/', {
            'ia_enabled': True
        })
        
        assert response.status_code == 200
        assert response.data['ia_status'] == 'ia_pending'

    def test_license_limit_prevents_creation(self):
        """Limite de licença deve impedir criação de câmera"""
        self.client.force_authenticate(user=self.admin)
        
        # Cria 2 câmeras (limite da licença)
        for i in range(2):
            Camera.objects.create(
                tenant=self.tenant,
                name=f'Câmera {i}',
                address='Test',
                latitude=-23.5505,
                longitude=-46.6333,
                stream_protocol='rtsp'
            )
        
        # Tenta criar a 3ª câmera
        response = self.client.post('/api/v1/cameras/', {
            'name': 'Câmera 3',
            'address': 'Test',
            'latitude': -23.5505,
            'longitude': -46.6333,
            'stream_protocol': 'rtsp'
        })
        
        assert response.status_code == 403
        assert 'limite' in response.data['detail'].lower()

    def test_operator_cannot_create_camera(self):
        """Operador não pode criar câmera"""
        operator = UserFactory(role='operator', tenant=self.tenant, password='pass123')
        self.client.force_authenticate(user=operator)
        
        response = self.client.post('/api/v1/cameras/', {
            'name': 'Câmera Test',
            'address': 'Test',
            'latitude': -23.5505,
            'longitude': -46.6333,
            'stream_protocol': 'rtsp'
        })
        
        assert response.status_code == 403

    def test_camera_from_other_tenant_returns_404(self):
        """Câmera de outro tenant deve retornar 404"""
        other_tenant = TenantFactory()
        other_camera = Camera.objects.create(
            tenant=other_tenant,
            name='Other Camera',
            address='Test',
            latitude=-23.5505,
            longitude=-46.6333,
            stream_protocol='rtsp'
        )
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/v1/cameras/{other_camera.id}/')
        
        assert response.status_code == 404

    def test_list_cameras_filtered_by_tenant(self):
        """Listagem deve filtrar por tenant automaticamente"""
        # Câmera do tenant atual
        Camera.objects.create(
            tenant=self.tenant,
            name='My Camera',
            address='Test',
            latitude=-23.5505,
            longitude=-46.6333,
            stream_protocol='rtsp'
        )
        
        # Câmera de outro tenant
        other_tenant = TenantFactory()
        Camera.objects.create(
            tenant=other_tenant,
            name='Other Camera',
            address='Test',
            latitude=-23.5505,
            longitude=-46.6333,
            stream_protocol='rtsp'
        )
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/cameras/')
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == 'My Camera'
