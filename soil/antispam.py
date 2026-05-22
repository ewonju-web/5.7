"""현장 자재 나눔 게시판 봇·도배 방지."""
import re
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import quote

from equipment.models import Profile

SOIL_POSTS_PER_HOUR = 5
SOIL_POSTS_PER_DAY = 20
SOIL_POSTS_PER_IP_HOUR = 15

_SPAM_TITLE_RE = re.compile(
    r'^(mr\.?|mrs\.?|ms\.?|dr\.?|test|asdf|aaa+|xxx+)$',
    re.I,
)

# SQL 인젝션·스캐너 봇 페이로드
_ATTACK_PATTERNS = re.compile(
    r'('
    r'pg_sleep\s*\(|benchmark\s*\(|sleep\s*\(|waitfor\s+delay|sysdate\s*\(\s*\)'
    r'|dbms_pipe|receive_message|chr\s*\(\s*\d+'
    r'|select\s+.+\s+from|union\s+select|insert\s+into|drop\s+table|delete\s+from'
    r'|\bor\s+[\d\'"]|\bor\s+\d+\s*[=+-]|\bxor\s*\(|\'\s*\|\||"\s*\|\|'
    r'|\'\s*or\s+|"\s*or\s+|-1\s+or\s+'
    r'|--\s*$|/\*|\*/|;--|%2527|%2522'
    r'|\(select\s*\(|information_schema|concat\s*\(|char\s*\('
    r'|@@[a-z0-9]{3,}'
    r')',
    re.I,
)

# Mr.랜덤문자열 + 공격 코드 형태 (스캐너가 제목란에 넣는 패턴)
_MR_ATTACK_TITLE_RE = re.compile(
    r'^mr\.?[a-z0-9]{4,}.*('
    r'select|sleep|waitfor|xor|pg_sleep|or\s+\d+\s*='
    r')',
    re.I,
)


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or 'unknown'


def require_phone_for_soil_post(request):
    """현장 자재 글쓰기: 휴대폰 본인인증 필수(스태프 제외)."""
    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.is_staff or request.user.is_superuser:
        return None
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)
    if not getattr(profile, 'phone_verified', False):
        next_path = request.get_full_path()
        return redirect(reverse('phone_verify') + '?next=' + quote(next_path, safe=''))
    return None


def check_soil_rate_limit(request):
    """
    사용자·IP별 등록 횟수 제한.
    통과 시 None, 초과 시 사용자에게 보여줄 오류 메시지 문자열.
    """
    user = request.user
    ip = _client_ip(request)
    hour_key_u = f'soil_rl:u{user.id}:h'
    day_key_u = f'soil_rl:u{user.id}:d'
    hour_key_ip = f'soil_rl:ip:{ip}:h'

    hour_count = cache.get(hour_key_u, 0)
    day_count = cache.get(day_key_u, 0)
    ip_hour = cache.get(hour_key_ip, 0)

    if hour_count >= SOIL_POSTS_PER_HOUR:
        return '짧은 시간에 너무 많이 등록했습니다. 1시간 후 다시 시도해 주세요.'
    if day_count >= SOIL_POSTS_PER_DAY:
        return '오늘 등록 가능 횟수를 초과했습니다. 내일 다시 시도해 주세요.'
    if ip_hour >= SOIL_POSTS_PER_IP_HOUR:
        return '접속 IP에서 등록이 과도합니다. 잠시 후 다시 시도해 주세요.'
    return None


def bump_soil_rate_limit(request):
    user = request.user
    ip = _client_ip(request)
    hour_key_u = f'soil_rl:u{user.id}:h'
    day_key_u = f'soil_rl:u{user.id}:d'
    hour_key_ip = f'soil_rl:ip:{ip}:h'

    cache.set(hour_key_u, cache.get(hour_key_u, 0) + 1, 3600)
    cache.set(day_key_u, cache.get(day_key_u, 0) + 1, 86400)
    cache.set(hour_key_ip, cache.get(hour_key_ip, 0) + 1, 3600)


def _text_has_attack_payload(*parts):
    for part in parts:
        text = (part or '').strip()
        if not text:
            continue
        if _ATTACK_PATTERNS.search(text):
            return True
        if _MR_ATTACK_TITLE_RE.match(text):
            return True
    return False


def validate_soil_post_content(title, location, contact='', description='', quantity='', note=''):
    """봇이 자주 쓰는 패턴·빈 값 도배·SQL 인젝션 차단."""
    title_s = (title or '').strip()
    loc_s = (location or '').strip()
    contact_s = (contact or '').strip()

    if len(title_s) < 4:
        raise ValidationError('제목을 4자 이상 입력해 주세요.')
    if _SPAM_TITLE_RE.match(title_s):
        raise ValidationError('제목 형식이 올바르지 않습니다.')
    if _text_has_attack_payload(title_s, loc_s, contact_s, description, quantity, note):
        raise ValidationError('허용되지 않는 문자가 포함되어 있습니다.')
    if len(loc_s) < 2:
        raise ValidationError('지역을 정확히 입력해 주세요.')
    if loc_s in ('1', '-', '.', 'test', 'asdf'):
        raise ValidationError('지역을 정확히 입력해 주세요.')
    if contact_s in ('1', '-', '1', 'test'):
        raise ValidationError('연락처를 정확히 입력해 주세요.')
    if title_s.lower() == loc_s.lower() == contact_s.lower() and title_s:
        raise ValidationError('입력 내용을 확인해 주세요.')

    combined = ' '.join([title_s, loc_s, contact_s, (description or ''), (quantity or ''), (note or '')])
    url_count = len(re.findall(r'https?://|www\.', combined, re.I))
    if url_count > 2:
        raise ValidationError('외부 링크가 너무 많습니다.')


def is_obvious_soil_spam(post):
    """관리·일괄 비활성화용 휴리스틱."""
    title = (post.title or '').strip()
    loc = (post.location or '').strip()
    contact = (getattr(post, 'contact', '') or '').strip()
    desc = (getattr(post, 'description', '') or '').strip()
    note = (getattr(post, 'note', '') or '').strip()
    qty = (getattr(post, 'quantity', '') or '').strip()
    if _SPAM_TITLE_RE.match(title):
        return True
    if _text_has_attack_payload(title, loc, contact, desc, note, qty):
        return True
    if title.lower() in ('mr', 'mrs', 'ms') and loc in ('1', '-') and contact in ('1', '-', ''):
        return True
    if len(title) < 4 and loc in ('1', 'test', ''):
        return True
    if title.startswith('Mr.') and len(title) > 6 and loc in ('1', '-', ''):
        # Mr. + 공격/깨진문자 제목 + placeholder 지역
        if not re.search(r'[가-힣]{2,}', title):
            return True
    if title.startswith('@@') or title.startswith('-1 OR'):
        return True
    if re.match(r'^mr\.?[\s\'"\\|%-]+$', title, re.I):
        return True
    return False
