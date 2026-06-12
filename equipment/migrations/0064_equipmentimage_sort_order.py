from django.db import migrations, models


def backfill_image_sort_order(apps, schema_editor):
    EquipmentImage = apps.get_model('equipment', 'EquipmentImage')
    equipment_ids = (
        EquipmentImage.objects.order_by()
        .values_list('equipment_id', flat=True)
        .distinct()
    )
    for equipment_id in equipment_ids:
        for order, img in enumerate(
            EquipmentImage.objects.filter(equipment_id=equipment_id).order_by('id')
        ):
            if img.sort_order != order:
                EquipmentImage.objects.filter(pk=img.pk).update(sort_order=order)


class Migration(migrations.Migration):

    dependencies = [
        ('equipment', '0063_jobpost_views'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipmentimage',
            name='sort_order',
            field=models.PositiveIntegerField(default=0, verbose_name='정렬 순서'),
        ),
        migrations.RunPython(backfill_image_sort_order, migrations.RunPython.noop),
    ]
