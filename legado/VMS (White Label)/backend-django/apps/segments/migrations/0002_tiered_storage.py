# Storage Sprint 2: Tiered Storage + Purge Inteligente

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('segments', '0001_initial'),
        ('tenants', '__first__'),
        ('cameras', '__first__'),
    ]

    operations = [
        # --- StoragePolicy ---
        migrations.CreateModel(
            name='StoragePolicy',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('category', models.CharField(choices=[
                    ('recordings', 'Gravações (segments)'),
                    ('snapshots', 'Snapshots (detecções)'),
                    ('heatmaps', 'Mapas de Calor'),
                    ('clips', 'Clips de Vídeo'),
                ], max_length=20)),
                ('tier_order', models.IntegerField(default=0)),
                ('path', models.CharField(help_text='Mount path dentro do container', max_length=500)),
                ('max_age_hours', models.IntegerField(blank=True, help_text='Idade máxima em horas', null=True)),
                ('max_size_gb', models.FloatField(blank=True, help_text='Tamanho máximo do tier em GB', null=True)),
                ('enabled', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='storage_policies', to='tenants.tenant')),
            ],
            options={
                'db_table': 'storage_policies',
                'ordering': ['tenant', 'category', 'tier_order'],
                'unique_together': {('tenant', 'category', 'tier_order')},
                'indexes': [
                    models.Index(fields=['tenant', 'category', 'enabled'], name='storage_po_tenant__abc123_idx'),
                ],
            },
        ),

        # --- StorageFile ---
        migrations.CreateModel(
            name='StorageFile',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('category', models.CharField(choices=[
                    ('snapshot', 'Snapshot de Detecção'),
                    ('heatmap', 'Mapa de Calor'),
                    ('clip', 'Clip de Vídeo'),
                ], max_length=20)),
                ('subcategory', models.CharField(blank=True, default='', help_text='Ex: lpr, facial, crowd', max_length=30)),
                ('file_path', models.CharField(db_index=True, max_length=500, unique=True)),
                ('file_size', models.BigIntegerField(default=0)),
                ('tier_order', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='storage_files', to='tenants.tenant')),
                ('camera', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='storage_files', to='cameras.camera')),
            ],
            options={
                'db_table': 'storage_files',
                'indexes': [
                    models.Index(fields=['tenant', 'category', 'created_at'], name='storage_fi_tenant__def456_idx'),
                    models.Index(fields=['camera', 'category', 'subcategory'], name='storage_fi_camera__ghi789_idx'),
                    models.Index(fields=['tier_order', 'created_at'], name='storage_fi_tier_or_jkl012_idx'),
                ],
            },
        ),

        # --- Segment: adicionar tier_order ---
        migrations.AddField(
            model_name='segment',
            name='tier_order',
            field=models.IntegerField(default=0),
        ),
        migrations.AddIndex(
            model_name='segment',
            index=models.Index(fields=['tier_order', 'created_at'], name='segments_tier_or_mno345_idx'),
        ),
    ]
