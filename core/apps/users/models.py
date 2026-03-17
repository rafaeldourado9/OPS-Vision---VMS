"""Models para users e tenants."""
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models


class Tenant(models.Model):
    """Tenant para multi-tenancy."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Reconhecimento Facial (LGPD) ──────────────────────────────────────────
    # Nunca habilitar sem aceite explícito do termo de consentimento.
    facial_recognition_enabled = models.BooleanField(
        default=False,
        help_text="Habilita reconhecimento facial. Requer aceite do termo LGPD.",
    )
    facial_recognition_consent_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Data/hora do aceite do termo de consentimento LGPD.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class UserManager(DjangoUserManager):
    """Manager customizado que garante tenant ao criar superusuário."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        """Cria superusuário, criando tenant 'Default' se não informado."""
        if "tenant" not in extra_fields and "tenant_id" not in extra_fields:
            tenant, _ = Tenant.objects.get_or_create(
                slug="default",
                defaults={"name": "Default"},
            )
            extra_fields["tenant"] = tenant
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """User customizado com tenant."""

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="users",
    )

    objects = UserManager()

    class Meta:
        ordering = ["username"]
