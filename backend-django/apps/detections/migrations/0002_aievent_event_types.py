from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('detections', '0001_initial'),
    ]

    operations = [
        # Atualiza choices do event_type (sem alteração de schema no DB)
        migrations.AlterField(
            model_name='aievent',
            name='event_type',
            field=models.CharField(
                choices=[
                    ('lpr', 'Reconhecimento de Placa'),
                    ('crowd', 'Aglomeração'),
                    ('intrusion', 'Intrusão'),
                    ('object_detected', 'Objeto Detectado'),
                    ('vehicle_traffic', 'Tráfego de Veículos'),
                    ('human_traffic', 'Tráfego Humano'),
                    ('line_crossing', 'Cruzamento de Linha'),
                    ('loitering', 'Perambulação'),
                    ('abandoned_object', 'Objeto Abandonado'),
                    ('queue_alert', 'Alerta de Fila'),
                    ('facial_match', 'Reconhecimento Facial - Match'),
                    ('facial_unknown', 'Pessoa Desconhecida'),
                ],
                max_length=20,
            ),
        ),
    ]
