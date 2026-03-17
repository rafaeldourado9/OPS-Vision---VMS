import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0001_initial'),
        ('cameras', '0003_camera_agent'),
        ('users', '0003_tenant_facial_recognition'),
    ]

    operations = [
        migrations.CreateModel(
            name='FaceProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('cpf', models.CharField(blank=True, max_length=14)),
                ('notes', models.TextField(blank=True)),
                ('embedding', models.JSONField()),
                ('photo_path', models.CharField(blank=True, max_length=512)),
                ('lgpd_consent', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='face_profiles', to='users.tenant')),
            ],
            options={'ordering': ['name']},
        ),
        migrations.AddIndex(
            model_name='faceprofile',
            index=models.Index(fields=['tenant'], name='analytics_f_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='faceprofile',
            index=models.Index(fields=['tenant', 'cpf'], name='analytics_f_tenant_cpf_idx'),
        ),
        migrations.CreateModel(
            name='FaceDetectionEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('confidence', models.FloatField(default=0.0)),
                ('is_unknown', models.BooleanField(default=False)),
                ('frame_path', models.CharField(blank=True, max_length=512)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('camera', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='face_events', to='cameras.camera')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='face_events', to='users.tenant')),
                ('roi', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='face_events', to='analytics.regionofinterest')),
                ('face_profile', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='detection_events', to='analytics.faceprofile')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='facedetectionevent',
            index=models.Index(fields=['tenant', '-created_at'], name='analytics_f_tenant_dt_idx'),
        ),
        migrations.AddIndex(
            model_name='facedetectionevent',
            index=models.Index(fields=['camera', '-created_at'], name='analytics_f_camera_dt_idx'),
        ),
        migrations.AddIndex(
            model_name='facedetectionevent',
            index=models.Index(fields=['tenant', 'is_unknown'], name='analytics_f_tenant_unk_idx'),
        ),
    ]
