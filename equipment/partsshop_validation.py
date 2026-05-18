# -*- coding: utf-8 -*-
import re

_HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")
_SQL_INJECTION_RE = re.compile(
    r"(select\s*\(|sleep\s*\(|union\s+select|/\*|\*/|--|0x[0-9a-f]|\bor\b\s+\d|@@\w+)",
    re.IGNORECASE,
)
_PHONE_DIGITS_RE = re.compile(r"\D")


def normalize_phone_digits(value: str) -> str:
    return _PHONE_DIGITS_RE.sub("", (value or "").strip())


def is_valid_korean_phone(value: str) -> bool:
    digits = normalize_phone_digits(value)
    if len(digits) < 8:
        return False
    # 일반 전화(0xx) 및 대표번호(15xx, 16xx, 18xx 등)
    return digits[0] in ("0", "1")


def contains_sql_injection(value: str) -> bool:
    return bool(_SQL_INJECTION_RE.search(value or ""))


def is_partsshop_spam(shop) -> bool:
    """스캐너/SQL 인젝션으로 오염된 부품점 레코드 여부."""
    fields = [shop.name, shop.region, shop.address, shop.contact, shop.note]
    if any(contains_sql_injection(field) for field in fields):
        return True
    if not _HANGUL_RE.search(shop.name or ""):
        return True
    if not _HANGUL_RE.search(shop.region or ""):
        return True
    if not is_valid_korean_phone(shop.contact):
        return True
    return False


def validate_partsshop_form(*, name: str, region: str, contact: str, address: str = "", note: str = "") -> str | None:
    """유효하면 None, 오류 메시지 문자열 반환."""
    fields = {
        "업체명": name,
        "지역": region,
        "연락처": contact,
        "주소": address,
        "비고": note,
    }
    for label, value in fields.items():
        if value and contains_sql_injection(value):
            return f"{label}에 허용되지 않는 문자가 포함되어 있습니다."
    if not _HANGUL_RE.search(name):
        return "업체명은 한글을 포함해 주세요."
    if not _HANGUL_RE.search(region):
        return "지역은 한글로 입력해 주세요. (예: 서울, 경기)"
    if not is_valid_korean_phone(contact):
        return "연락처는 0으로 시작하는 유효한 전화번호로 입력해 주세요."
    return None
