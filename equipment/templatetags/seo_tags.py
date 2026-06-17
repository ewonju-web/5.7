from django import template

from equipment.seo_meta import equipment_seo_description, equipment_seo_title

register = template.Library()

register.simple_tag(equipment_seo_title)
register.simple_tag(equipment_seo_description)
