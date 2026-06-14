"""채팅 메시지 SQL 인젝션·도배 방지."""
import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError

from equipment.finance_security import get_client_ip

User = get_user_model()

CHAT_MESSAGE_MAX_LEN = 200
CHAT_MSG_PER_USER_MINUTE = 10
CHAT_MSG_PER_IP_MINUTE = 25
CHAT_IP_AUTO_BLOCK_THRESHOLD = 35
CHAT_IP_BLOCK_SECONDS = 86400
CHAT_RATE_WINDOW = 60

_CHAT_ATTACK_PATTERNS = re.compile(
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

_CHAT_SUSPICIOUS_CHARS = re.compile(
    r'['
    r'\'"'
    r'='
    r']',
)

_CHAT_BLOCKED_IP_PREFIX = 'chat_block_ip:'
_CHAT_RL_USER_PREFIX = 'chat_rl:u:'
_CHAT_RL_IP_PREFIX = 'chat_rl:ip:'


class ChatBlockedError(ValidationError):
    """채팅 이용 제한."""


def is_ip_chat_blocked(ip: str) -> bool:
    ip = (ip or '').strip() or 'unknown'
    return bool(cache.get(f'{_CHAT_BLOCKED_IP_PREFIX}{ip}'))


def block_chat_ip(ip: str, seconds: int = CHAT_IP_BLOCK_SECONDS) -> None:
    ip = (ip or '').strip() or 'unknown'
    cache.set(f'{_CHAT_BLOCKED_IP_PREFIX}{ip}', 1, max(60, seconds))


def is_user_chat_banned(user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if not user.is_active:
        return True
    try:
        return user.manner_score.tier == 'blocked'
    except Exception:
        return False


def ban_user_chat(user, *, deactivate: bool = True) -> None:
    """계정 채팅·로그인 차단."""
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


def validate_chat_message(text: str) -> str:
    """메시지 검증 후 정제된 문자열 반환."""
    msg = (text or '').strip()
    if not msg:
        raise ValidationError('메시지를 입력해 주세요.')
    if len(msg) > CHAT_MESSAGE_MAX_LEN:
        raise ValidationError(f'메시지는 {CHAT_MESSAGE_MAX_LEN}자 이내로 입력해 주세요.')
    if _CHAT_ATTACK_PATTERNS.search(msg):
        raise ValidationError('허용되지 않는 문자가 포함되어 있습니다.')
    if _CHAT_SUSPICIOUS_CHARS.search(msg):
        raise ValidationError('허용되지 않는 특수문자가 포함되어 있습니다.')
    lowered = msg.lower()
    for token in ('sleep', ' xor ', ' or ', 'union', 'select', 'drop', 'delete', 'insert'):
        if token.strip() in lowered.replace('(', ' ').replace(')', ' '):
            raise ValidationError('허용되지 않는 문자가 포함되어 있습니다.')
    return msg


def check_chat_rate_limit(request) -> str | None:
    """통과 시 None, 차단 시 사용자 메시지."""
    user = request.user
    ip = get_client_ip(request)

    if is_ip_chat_blocked(ip):
        return '비정상적인 요청이 감지되어 채팅이 일시 차단되었습니다.'

    user_key = f'{_CHAT_RL_USER_PREFIX}{user.id}'
    ip_key = f'{_CHAT_RL_IP_PREFIX}{ip}'
    user_count = cache.get(user_key, 0)
    ip_count = cache.get(ip_key, 0)

    if user_count >= CHAT_MSG_PER_USER_MINUTE:
        return '메시지를 너무 빠르게 보내고 있습니다. 잠시 후 다시 시도해 주세요.'
    if ip_count >= CHAT_MSG_PER_IP_MINUTE:
        block_chat_ip(ip)
        return '접속 IP에서 메시지가 과도합니다. 채팅이 일시 차단되었습니다.'
    return None


def bump_chat_rate_limit(request) -> None:
    user = request.user
    ip = get_client_ip(request)
    user_key = f'{_CHAT_RL_USER_PREFIX}{user.id}'
    ip_key = f'{_CHAT_RL_IP_PREFIX}{ip}'

    user_count = cache.get(user_key, 0) + 1
    ip_count = cache.get(ip_key, 0) + 1
    cache.set(user_key, user_count, CHAT_RATE_WINDOW)
    cache.set(ip_key, ip_count, CHAT_RATE_WINDOW)

    if ip_count >= CHAT_IP_AUTO_BLOCK_THRESHOLD:
        block_chat_ip(ip)
