import factory
from factory.django import DjangoModelFactory
from apps.cameras.models import Camera
from tests.factories import TenantFactory


class CameraFactory(DjangoModelFactory):
    class Meta:
        model = Camera

    tenant = factory.SubFactory(TenantFactory)
    name = factory.Sequence(lambda n: f'Câmera {n}')
    address = factory.Faker('address')
    latitude = factory.Faker('latitude')
    longitude = factory.Faker('longitude')
    stream_protocol = 'rtsp'
    stream_url = factory.Sequence(lambda n: f'rtsp://camera{n}.example.com/stream')
    retention_days = 7
    ia_enabled = False
    online = False
