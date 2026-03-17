import pytest
from rest_framework.test import APIClient
from tests.factories import UserFactory, TenantFactory
from tests.camera_factory import CameraFactory
from apps.roi.models import RegionOfInterest


@pytest.mark.django_db
class TestROI:
    
    def setup_method(self):
        self.client = APIClient()
        self.tenant = TenantFactory()
        self.admin = UserFactory(role='city_admin', tenant=self.tenant, password='pass123')
        self.camera = CameraFactory(tenant=self.tenant, ia_enabled=True, ia_status='ia_pending')

    def test_create_roi_changes_camera_to_active(self):
        """Criar ROI deve mudar câmera.ia_status para active"""
        self.client.force_authenticate(user=self.admin)
        
        response = self.client.post('/api/v1/roi/', {
            'camera': str(self.camera.id),
            'name': 'Zona 1',
            'polygon': [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            'ia_type': 'lpr'
        })
        
        assert response.status_code == 201
        
        self.camera.refresh_from_db()
        assert self.camera.ia_status == 'active'

    def test_delete_last_roi_changes_camera_to_pending(self):
        """Deletar último ROI deve mudar câmera.ia_status para ia_pending"""
        self.client.force_authenticate(user=self.admin)
        
        # Cria ROI
        roi = RegionOfInterest.objects.create(
            tenant=self.tenant,
            camera=self.camera,
            name='Zona 1',
            polygon=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            ia_type='lpr'
        )
        
        self.camera.ia_status = 'active'
        self.camera.save()
        
        # Deleta ROI
        response = self.client.delete(f'/api/v1/roi/{roi.id}/')
        
        assert response.status_code == 204
        
        self.camera.refresh_from_db()
        assert self.camera.ia_status == 'ia_pending'

    def test_roi_with_less_than_3_points_returns_400(self):
        """ROI com menos de 3 pontos deve retornar 400"""
        self.client.force_authenticate(user=self.admin)
        
        response = self.client.post('/api/v1/roi/', {
            'camera': str(self.camera.id),
            'name': 'Zona Inválida',
            'polygon': [[0.1, 0.1], [0.9, 0.1]],  # Apenas 2 pontos
            'ia_type': 'lpr'
        })
        
        assert response.status_code == 400

    def test_roi_from_other_tenant_returns_404(self):
        """ROI de outro tenant deve retornar 404"""
        other_tenant = TenantFactory()
        other_camera = CameraFactory(tenant=other_tenant)
        other_roi = RegionOfInterest.objects.create(
            tenant=other_tenant,
            camera=other_camera,
            name='Other ROI',
            polygon=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]],
            ia_type='lpr'
        )
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/v1/roi/{other_roi.id}/')
        
        assert response.status_code == 404

    def test_list_roi_filtered_by_camera(self):
        """Listagem deve filtrar por camera_id"""
        camera2 = CameraFactory(tenant=self.tenant)
        
        roi1 = RegionOfInterest.objects.create(
            tenant=self.tenant,
            camera=self.camera,
            name='ROI 1',
            polygon=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]],
            ia_type='lpr'
        )
        
        roi2 = RegionOfInterest.objects.create(
            tenant=self.tenant,
            camera=camera2,
            name='ROI 2',
            polygon=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]],
            ia_type='intrusion'
        )
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/v1/roi/?camera_id={self.camera.id}')
        
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['name'] == 'ROI 1'
