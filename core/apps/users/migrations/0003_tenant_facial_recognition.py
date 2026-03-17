from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_custom_user_manager'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='facial_recognition_enabled',
            field=models.BooleanField(default=False, help_text='Habilita reconhecimento facial. Requer aceite do termo LGPD.'),
        ),
        migrations.AddField(
            model_name='tenant',
            name='facial_recognition_consent_at',
            field=models.DateTimeField(blank=True, null=True, help_text='Data/hora do aceite do termo de consentimento LGPD.'),
        ),
    ]
