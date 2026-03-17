"""Management command para popular o banco com dados de desenvolvimento."""
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.cameras.models import Camera
from apps.users.models import Tenant

User = get_user_model()

_LOCATIONS = [
    "Entrada Principal",
    "Estacionamento",
    "Corredor A",
    "Corredor B",
    "Sala de Servidores",
    "Recepção",
    "Almoxarifado",
    "Portaria",
    "Refeitório",
    "Área Externa",
    "Garagem",
    "Telhado",
]

_MANUFACTURERS = [
    Camera.Manufacturer.INTELBRAS,
    Camera.Manufacturer.HIKVISION,
    Camera.Manufacturer.OTHER,
]


class Command(BaseCommand):
    help = "Popula o banco com dados de desenvolvimento"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--cameras",
            type=int,
            default=10,
            help="Número de câmeras a criar (padrão: 10)",
        )
        parser.add_argument(
            "--tenant",
            type=str,
            default="Demo",
            help="Nome do tenant (padrão: Demo)",
        )
        parser.add_argument(
            "--username",
            type=str,
            default="admin",
            help="Username do usuário admin (padrão: admin)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="admin123",
            help="Senha do usuário admin (padrão: admin123)",
        )

    def handle(self, *args, **options) -> None:
        tenant_name: str = options["tenant"]
        username: str = options["username"]
        password: str = options["password"]
        camera_count: int = options["cameras"]

        # Tenant
        tenant, tenant_created = Tenant.objects.get_or_create(
            slug=tenant_name.lower(),
            defaults={"name": tenant_name},
        )
        if tenant_created:
            self.stdout.write(f"  Tenant '{tenant.name}' criado.")
        else:
            self.stdout.write(f"  Tenant '{tenant.name}' já existe.")

        # Usuário admin
        user, user_created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": f"{username}@demo.local",
                "tenant": tenant,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if user_created:
            user.set_password(password)
            user.save()
            self.stdout.write(
                f"  Usuário '{username}' criado com senha '{password}'."
            )
        else:
            self.stdout.write(
                f"  Usuário '{username}' já existe (senha não alterada)."
            )

        # Câmeras
        cameras_created = 0
        locations = _LOCATIONS * (camera_count // len(_LOCATIONS) + 1)
        for i in range(camera_count):
            location = locations[i]
            name = f"Cam {i + 1:02d} — {location}"
            if Camera.objects.filter(tenant=tenant, name=name).exists():
                continue
            Camera.objects.create(
                name=name,
                location=location,
                rtsp_url=f"rtsp://192.168.1.{10 + i}:554/stream",
                manufacturer=random.choice(_MANUFACTURERS),
                retention_days=random.choice([7, 15, 30]),
                is_online=random.choice([True, True, True, False]),
                tenant=tenant,
            )
            cameras_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeed concluído: tenant='{tenant.name}', "
                f"user='{username}', cameras={cameras_created} criadas."
            )
        )
        if user_created:
            self.stdout.write(
                self.style.WARNING(
                    f"  Login: {username} / {password}"
                )
            )
