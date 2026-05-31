from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("equipment", "0057_driverprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="profile_photo",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="profile_photos/",
                verbose_name="명함 사진",
            ),
        ),
    ]
