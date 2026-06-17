from django import template

from equipment.schema_markup import render_equipment_schema_script
from equipment.seo_meta import equipment_seo_description, equipment_seo_title

register = template.Library()

register.simple_tag(equipment_seo_title)
register.simple_tag(equipment_seo_description)


@register.simple_tag
def equipment_schema_ld_json(equipment, request, detail_images=None):
    return render_equipment_schema_script(equipment, request, detail_images or [])
