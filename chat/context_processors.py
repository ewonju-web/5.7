from django.db.models import Q

from equipment.templatetags.i18n_extras import SUPPORTED_LANGS
from equipment.i18n.page_messages import get_page_dict
from equipment.i18n.seo_i18n import SEO_HREFLANG_CODES, get_og_locale, get_seo_meta
from .models import ChatMessage


def lang(request):
    """템플릿에서 사용할 언어 코드. 세션에 없으면 'ko'."""
    code = (request.session.get('lang') or 'ko').strip().lower()
    if code not in SUPPORTED_LANGS:
        code = 'ko'
    return {
        'LANG': code,
        'I18N_PAGE': get_page_dict(code),
        'SEO_META': get_seo_meta(code),
        'OG_LOCALE': get_og_locale(code),
        'SEO_HREFLANG_CODES': SEO_HREFLANG_CODES,
    }


def chat_unread(request):
    """로그인 사용자의 채팅 미읽음 메시지 총개수. 상단 '채팅' 메뉴 뱃지용."""
    unread_total = 0
    if getattr(request, 'user', None) and request.user.is_authenticated:
        unread_total = (
            ChatMessage.objects.filter(is_read=False)
            .exclude(sender=request.user)
            .filter(Q(room__buyer=request.user) | Q(room__seller=request.user))
            .count()
        )
    return {'unread_total': unread_total}
