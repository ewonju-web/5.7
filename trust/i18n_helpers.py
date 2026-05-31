from equipment.templatetags.i18n_extras import translate

from .models import ReviewBadTag, SellerReport


def request_lang(request) -> str:
    code = (request.session.get('lang') or 'ko').strip().lower()
    return code


def translated_bad_tag_choices(request):
    lang = request_lang(request)
    return [
        (val, translate(lang, f'trust_bad_{val}'))
        for val, _ in ReviewBadTag.TAG_CHOICES
    ]


def translated_report_choices(request):
    lang = request_lang(request)
    return [
        (val, translate(lang, f'trust_report_{val}'))
        for val, _ in SellerReport.REPORT_CHOICES
    ]
