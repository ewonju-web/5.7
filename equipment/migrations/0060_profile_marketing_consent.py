from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('equipment', '0059_examattachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='marketing_consent',
            field=models.BooleanField(default=False, verbose_name='마케팅 수신 동의'),
        ),
        migrations.AddField(
            model_name='profile',
            name='marketing_consent_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='마케팅 수신 동의 시각'),
        ),
    ]
