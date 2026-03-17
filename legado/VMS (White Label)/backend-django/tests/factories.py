import factory
from factory.django import DjangoModelFactory
from apps.resellers.models import Reseller
from apps.franchise.models import License
from apps.tenants.models import Tenant
from apps.auth_app.models import User
from datetime import date, timedelta


class ResellerFactory(DjangoModelFactory):
    class Meta:
        model = Reseller

    name = factory.Faker('company')
    slug = factory.Sequence(lambda n: f'reseller-{n}')
    custom_domain = factory.Sequence(lambda n: f'reseller{n}.example.com')
    primary_color = '#1E40AF'
    secondary_color = '#3B82F6'
    active = True


class LicenseFactory(DjangoModelFactory):
    class Meta:
        model = License

    reseller = factory.SubFactory(ResellerFactory)
    max_cameras = 10
    valid_until = date.today() + timedelta(days=365)
    active = True


class TenantFactory(DjangoModelFactory):
    class Meta:
        model = Tenant

    reseller = factory.SubFactory(ResellerFactory)
    license = factory.SubFactory(LicenseFactory)
    name = factory.Faker('city')
    subdomain = factory.Sequence(lambda n: f'city{n}')
    active = True


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Faker('email')
    tenant = factory.SubFactory(TenantFactory)
    role = 'operator'
    active = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.set_password(extracted)
        else:
            self.set_password('testpass123')
