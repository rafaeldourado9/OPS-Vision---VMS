import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='KnownPerson',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('photo', models.ImageField(upload_to='persons/%Y%m/')),
                ('notes', models.TextField(blank=True)),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='known_persons',
                    to='tenants.tenant',
                )),
            ],
            options={
                'db_table': 'known_persons',
                'ordering': ['name'],
                'indexes': [
                    models.Index(fields=['tenant', 'active'], name='known_perso_tenant__active_idx'),
                ],
            },
        ),
    ]
