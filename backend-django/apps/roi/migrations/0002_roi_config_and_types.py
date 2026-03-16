from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('roi', '0001_initial'),
    ]

    operations = [
        # Adiciona campo config
        migrations.AddField(
            model_name='regionofinterest',
            name='config',
            field=models.JSONField(blank=True, default=dict),
        ),
        # Atualiza choices do ia_type (sem alteração de schema no DB)
        migrations.AlterField(
            model_name='regionofinterest',
            name='ia_type',
            field=models.CharField(
                choices=[
                    ('lpr', 'Reconhecimento de Placas'),
                    ('crowd', 'Detecção de Multidões'),
                    ('intrusion', 'Intrusão'),
                    ('object_detection', 'Detecção de Objetos'),
                    ('vehicle_traffic', 'Tráfego de Veículos'),
                    ('human_traffic', 'Tráfego Humano'),
                    ('line_crossing', 'Cruzamento de Linha'),
                    ('loitering', 'Perambulação'),
                    ('abandoned_object', 'Objeto Abandonado'),
                    ('queue', 'Detecção de Fila'),
                    ('facial', 'Reconhecimento Facial'),
                    ('heatmap', 'Mapa de Calor'),
                ],
                max_length=20,
            ),
        ),
    ]
