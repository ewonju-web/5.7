"""사이트 전역 사용자 입력 SQLi·도배 방어."""
from __future__ import annotations

import json
import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError

from equipment.finance_security import get_client_ip

User = get_user_model()

# --- 공격 패턴 (soil/chat 통합) ---
ATTACK_PATTERNS = re.compile(
    r'('
    r'pg_sleep\s*\(|benchmark\s*\(|sleep\s*\(|waitfor\s+delay|sysdate\s*\(\s*\)'
    r'|dbms_pipe|receive_message|chr\s*\(\s*\d+'
    r'|select\s+.+\s+from|union\s+select|insert\s+into|drop\s+table|delete\s+from'
    r'|\bor\s+[\d\'"]|\bor\s+\d+\s*[=+-]|\bxor\s*\(|\'\s*\|\||"\s*\|\|'
    r'|\'\s*or\s+|"\s*or\s+|-1\s+or\s+'
    r'|--\s*$|/\*|\*/|;--|%2527|%2522'
    r'|\(select\s*\(|information_schema|concat\s*\(|char\s*\('
    r'|@@[a-z0-9]{3,}|if\s*\(\s*now\s*\(\s*\)\s*='
    r')',
    re.I,
)

MR_ATTACK_TITLE_RE = re.compile(
    r'^mr\.?[a-z0-9]{4,}.*('
    r'select|sleep|waitfor|xor|pg_sleep|or\s+\d+\s*='
    r')',
    re.I,
)

ATTACK_TOKENS = ('sleep', ' xor ', ' or ', 'union', 'select', 'drop', 'delete', 'insert')

FIELD_MAX_LENGTHS = {
    'title': 200,
    'name': 100,
    'content': 2000,
    'message': 200,
    'comment': 500,
    'description': 2000,
    'memo': 500,
    'note': 1000,
    'bio': 30,
    'detail': 2000,
    'youtube_url': 300,
    'location': 100,
    'contact': 50,
    'manufacturer': 50,
    'model_name': 100,
}
DEFAULT_FIELD_MAX = 500

SKIP_POST_FIELDS = frozenset({
    'csrfmiddlewaretoken',
    'password', 'password1', 'password2',
    'old_password', 'new_password1', 'new_password2',
    'g-recaptcha-response', 'captcha', 'hp', 'company_url',
    'listing_id', 'equipment_id', 'seller_id', 'room_id',
    'delete_image_ids', 'action', 'category', 'equipment',
    'equipment_type', 'review_type', 'reason', 'sort', 'page',
    'month_manufactured', 'year_manufactured', 'operating_hours',
    'listing_price', 'listing_status', 'is_sold',
})

WRITE_RL_USER_MINUTE = 8
WRITE_RL_USER_HOUR = 30
WRITE_RL_IP_MINUTE = 15
WRITE_RL_IP_HOUR = 40
WRITE_IP_BLOCK_THRESHOLD = 60
WRITE_IP_BLOCK_SECONDS = 86400
WRITE_RATE_MINUTE = 60
WRITE_RATE_HOUR = 3600

_BLOCKED_IP_PREFIX = 'sec_block_ip:'
_WRITE_RL_USER_MIN = 'write_rl:u:{}:m'
_WRITE_RL_USER_HOUR = 'write_rl:u:{}:h'
_WRITE_RL_IP_MIN = 'write_rl:ip:{}:m'
_WRITE_RL_IP_HOUR = 'write_rl:ip:{}:h'
_ATTACK_COUNT_USER = 'write_attack:u:{}'


def max_len_for_field(field_name: str) -> int:
    key = (field_name or '').lower()
    for token, limit in FIELD_MAX_LENGTHS.items():
        if token in key:
            return limit
    return DEFAULT_FIELD_MAX


def _token_matches_normalized(token: str, normalized: str) -> bool:
    """SQL 키워드/토큰 매칭. strip()으로 ' or '→'or'가 되면 excavator 등 정상 영어도 오탐한다."""
    if not token:
        return False
    # 공백으로 감싼 토큰(' or ', ' xor ')은 부분문자열이 아니라 구분자 포함 매칭
    if token[0].isspace() or token[-1].isspace():
        return token in f' {normalized} '
    # sleep/select 등은 단어 경계로만 매칭 (operator·excavator 오탐 방지)
    return bool(
        re.search(
            rf'(?<![a-z0-9_]){re.escape(token)}(?![a-z0-9_])',
            normalized,
        )
    )


def text_has_attack_payload(*parts: str) -> bool:
    for part in parts:
        text = (part or '').strip()
        if not text:
            continue
        if ATTACK_PATTERNS.search(text):
            return True
        if MR_ATTACK_TITLE_RE.match(text):
            return True
        lowered = text.lower()
        normalized = lowered.replace('(', ' ').replace(')', ' ')
        for token in ATTACK_TOKENS:
            if _token_matches_normalized(token, normalized):
                return True
        if text.startswith('@@') or text.startswith('-1 OR'):
            return True
    return False


def validate_user_text(text: str, *, field_name: str = 'content', required: bool = False) -> str:
    value = (text or '').strip()
    if not value:
        if required:
            raise ValidationError(f'{field_name}을(를) 입력해 주세요.')
        return ''
    max_len = max_len_for_field(field_name)
    if len(value) > max_len:
        raise ValidationError(f'{field_name}은(는) {max_len}자 이내로 입력해 주세요.')
    if text_has_attack_payload(value):
        raise ValidationError('허용되지 않는 문자가 포함되어 있습니다.')
    return value


def is_ip_blocked(ip: str) -> bool:
    ip = (ip or '').strip() or 'unknown'
    try:
        from equipment.bot_blocklist import is_blocked_bot_ip

        if is_blocked_bot_ip(ip):
            return True
    except Exception:
        pass
    return bool(cache.get(f'{_BLOCKED_IP_PREFIX}{ip}'))


def block_ip(ip: str, seconds: int = WRITE_IP_BLOCK_SECONDS) -> None:
    ip = (ip or '').strip() or 'unknown'
    cache.set(f'{_BLOCKED_IP_PREFIX}{ip}', 1, max(60, seconds))


def ban_user_account(user, *, deactivate: bool = True) -> None:
    if not user or not user.pk:
        return
    if deactivate and user.is_active:
        user.is_active = False
        user.save(update_fields=['is_active'])
    try:
        from trust.models import MannerScore

        MannerScore.objects.update_or_create(
            user=user,
            defaults={'score': 0.0, 'tier': 'blocked'},
        )
    except Exception:
        pass


def iter_post_text_values(request) -> list[tuple[str, str]]:
    """POST/JSON 본문에서 검사할 (필드명, 값) 목록."""
    pairs: list[tuple[str, str]] = []
    for key, values in request.POST.lists():
        if key in SKIP_POST_FIELDS:
            continue
        for raw in values:
            if isinstance(raw, str) and raw.strip():
                pairs.append((key, raw))
    content_type = (request.META.get('CONTENT_TYPE') or '').lower()
    if 'application/json' in content_type and request.body:
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            for key, raw in payload.items():
                if key in SKIP_POST_FIELDS:
                    continue
                if isinstance(raw, str) and raw.strip():
                    pairs.append((key, raw))
    return pairs


def validate_request_post_data(request) -> str | None:
    """통과 시 None, 차단 시 사용자 메시지."""
    for field_name, raw in iter_post_text_values(request):
        try:
            validate_user_text(raw, field_name=field_name)
        except ValidationError as exc:
            return exc.messages[0] if exc.messages else '입력값을 확인해 주세요.'
    return None


def check_write_rate_limit(request) -> str | None:
    ip = get_client_ip(request)
    if is_ip_blocked(ip):
        return '비정상적인 요청이 감지되어 접근이 일시 차단되었습니다.'

    user_id = request.user.pk if getattr(request.user, 'is_authenticated', False) else 'anon'
    keys = {
        'u_min': _WRITE_RL_USER_MIN.format(user_id),
        'u_hour': _WRITE_RL_USER_HOUR.format(user_id),
        'ip_min': _WRITE_RL_IP_MIN.format(ip),
        'ip_hour': _WRITE_RL_IP_HOUR.format(ip),
    }
    u_min = cache.get(keys['u_min'], 0)
    u_hour = cache.get(keys['u_hour'], 0)
    ip_min = cache.get(keys['ip_min'], 0)
    ip_hour = cache.get(keys['ip_hour'], 0)

    if u_min >= WRITE_RL_USER_MINUTE or ip_min >= WRITE_RL_IP_MINUTE:
        return '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.'
    if u_hour >= WRITE_RL_USER_HOUR or ip_hour >= WRITE_RL_IP_HOUR:
        block_ip(ip, seconds=3600)
        return '요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.'
    return None


def bump_write_rate_limit(request) -> None:
    ip = get_client_ip(request)
    user_id = request.user.pk if getattr(request.user, 'is_authenticated', False) else 'anon'
    for key_tpl, window in (
        (_WRITE_RL_USER_MIN, WRITE_RATE_MINUTE),
        (_WRITE_RL_USER_HOUR, WRITE_RATE_HOUR),
        (_WRITE_RL_IP_MIN, WRITE_RATE_MINUTE),
        (_WRITE_RL_IP_HOUR, WRITE_RATE_HOUR),
    ):
        if 'ip' in key_tpl:
            key = key_tpl.format(ip)
        else:
            key = key_tpl.format(user_id)
        cache.set(key, cache.get(key, 0) + 1, window)
    ip_hour = cache.get(_WRITE_RL_IP_HOUR.format(ip), 0)
    if ip_hour >= WRITE_IP_BLOCK_THRESHOLD:
        block_ip(ip)


def record_attack_attempt(request) -> bool:
    """공격 시도 기록. True면 계정 자동 차단."""
    ip = get_client_ip(request)
    block_ip(ip, seconds=3600)
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return False
    key = _ATTACK_COUNT_USER.format(user.pk)
    count = cache.get(key, 0) + 1
    cache.set(key, count, 3600)
    if count >= 2:
        ban_user_account(user)
        return True
    return False
