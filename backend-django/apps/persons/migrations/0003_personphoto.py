import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('persons', '0002_rename_known_perso_tenant__active_idx_known_perso_tenant__b5b705_idx'),
    ]

    operations = [
        migrations.CreateModel(
            name='PersonPhoto',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('photo', models.ImageField(upload_to='persons/%Y%m/')),
                ('label', models.CharField(blank=True, help_text='Ex: frontal, perfil_esquerdo, perfil_direito, oculos', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('person', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extra_photos', to='persons.knownperson')),
            ],
            options={
                'db_table': 'person_photos',
                'ordering': ['created_at'],
            },
        ),
    ]
