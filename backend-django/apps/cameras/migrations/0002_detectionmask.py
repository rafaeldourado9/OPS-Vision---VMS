import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cameras', '0001_initial'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DetectionMask',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(default='Mask', max_length=255)),
                ('polygon', models.JSONField(help_text='List of [x, y] normalized 0-1')),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('camera', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detection_masks', to='cameras.camera')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detection_masks', to='tenants.tenant')),
            ],
            options={
                'db_table': 'detection_masks',
                'indexes': [
                    models.Index(fields=['tenant', 'camera'], name='detection_m_tenant__9f4a2c_idx'),
                    models.Index(fields=['camera', 'active'], name='detection_m_camera__3b8e1f_idx'),
                ],
            },
        ),
    ]
