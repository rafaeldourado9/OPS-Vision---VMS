"""Factories para testes usando factory_boy."""
import secrets

import factory
from django.contrib.auth import get_user_model

User = get_user_model()


class TenantFactory(factory.django.DjangoModelFactory):
    """Factory para Tenant."""

    class Meta:
        model = "users.Tenant"
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Tenant {n}")
    slug = factory.Sequence(lambda n: f"tenant-{n}")


class UserFactory(factory.django.DjangoModelFactory):
    """Factory para User."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@test.com")
    tenant = factory.SubFactory(TenantFactory)
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


class CameraFactory(factory.django.DjangoModelFactory):
    """Factory para Camera."""

    class Meta:
        model = "cameras.Camera"

    name = factory.Sequence(lambda n: f"Camera {n}")
    location = factory.Faker("city", locale="pt_BR")
    rtsp_url = factory.Sequence(
        lambda n: f"rtsp://192.168.1.{n % 255}:554/stream"
    )
    manufacturer = "intelbras"
    retention_days = 7
    is_online = True
    agent = None
    tenant = factory.SubFactory(TenantFactory)


class AgentFactory(factory.django.DjangoModelFactory):
    """Factory para Agent."""

    class Meta:
        model = "agents.Agent"

    name = factory.Sequence(lambda n: f"Agent {n}")
    api_key = factory.LazyFunction(lambda: secrets.token_urlsafe(48))
    tenant = factory.SubFactory(TenantFactory)
    status = "pending"
    version = ""
    metadata = factory.LazyFunction(dict)


class EventFactory(factory.django.DjangoModelFactory):
    """Factory para Event."""

    class Meta:
        model = "events.Event"

    event_type = "alpr.detected"
    payload = factory.LazyFunction(dict)
    plate = factory.Faker("bothify", text="ABC####")
    confidence = factory.Faker("pyfloat", min_value=0.5, max_value=0.99)
    camera = factory.SubFactory(CameraFactory)
    tenant = factory.LazyAttribute(lambda o: o.camera.tenant)
