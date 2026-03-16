import uuid
from django.db import models


class KnownPerson(models.Model):
    """Pessoa cadastrada para reconhecimento facial."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE, related_name='known_persons'
    )
    name = models.CharField(max_length=255)
    photo = models.ImageField(upload_to='persons/%Y%m/')
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'known_persons'
        indexes = [
            models.Index(fields=['tenant', 'active']),
        ]
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.tenant.name})'


class PersonPhoto(models.Model):
    """
    Foto adicional de uma pessoa para reconhecimento facial multi-ângulo.
    Cada pessoa pode ter N fotos (frontal, perfil esquerdo, perfil direito, etc).
    O worker extrai um embedding de cada foto e usa o melhor match.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(
        KnownPerson, on_delete=models.CASCADE, related_name='extra_photos'
    )
    photo = models.ImageField(upload_to='persons/%Y%m/')
    label = models.CharField(
        max_length=50, blank=True,
        help_text='Ex: frontal, perfil_esquerdo, perfil_direito, oculos',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'person_photos'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.person.name} — {self.label or "extra"}'
