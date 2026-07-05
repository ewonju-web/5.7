from django import template

from equipment.schema_markup import render_equipment_schema_script
from equipment.seo_meta import equipment_seo_description as build_equipment_seo_description
from equipment.seo_meta import equipment_seo_title as build_equipment_seo_title
from equipment.templatetags.i18n_extras import SUPPORTED_LANGS

register = template.Library()


@register.simple_tag(takes_context=True)
def equipment_seo_title(context, equipment):
    lang = (context.get("LANG") or "ko").strip().lower()
    if lang not in SUPPORTED_LANGS:
        lang = "ko"
    return build_equipment_seo_title(equipment, lang=lang)


@register.simple_tag(takes_context=True)
def equipment_seo_description(context, equipment):
    lang = (context.get("LANG") or "ko").strip().lower()
    if lang not in SUPPORTED_LANGS:
        lang = "ko"
    return build_equipment_seo_description(equipment, lang=lang)


@register.simple_tag(takes_context=True)
def equipment_schema_ld_json(context, equipment, request, detail_images=None):
    lang = (context.get("LANG") or "ko").strip().lower()
    if lang not in SUPPORTED_LANGS:
        lang = "ko"
    return render_equipment_schema_script(equipment, request, detail_images or [], lang=lang)
