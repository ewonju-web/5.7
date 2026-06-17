"""검색엔진용 동적 sitemap.xml — 매물 추가/삭제 시 자동 반영(캐시 TTL)."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.utils import timezone

from .models import Equipment, EquipmentType

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
ET.register_namespace("", SITEMAP_NS)

SITEMAP_CACHE_KEY = "sitemap:xml:v2"
SITEMAP_CACHE_SECONDS = 3600  # 1시간마다 DB 기준으로 재생성

STATIC_PATHS = (
    "/",
    "/jobs/",
    "/jobs/exam/",
    "/jobs/exam/videos/",
    "/info/",
    "/parts-as/",
    "/finance/",
    "/company/",
    "/terms/",
    "/privacy/",
)

CATEGORY_PATHS = tuple(
    f"/?category={code}"
    for code, _label in EquipmentType.choices
    if code
)


def sitemap_base_url() -> str:
    domain = (getattr(settings, "SITE_DOMAIN", "") or "").strip().lower()
    if domain in ("direct-nara.co.kr", "www.direct-nara.co.kr"):
        return "https://www.direct-nara.co.kr"
    if domain and not domain.startswith("http"):
        return f"https://{domain}"
    return "https://www.direct-nara.co.kr"


def _format_lastmod(dt) -> str:
    if not dt:
        return ""
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return timezone.localtime(dt).date().isoformat()


def _append_url(
    urlset: ET.Element,
    base: str,
    path: str,
    *,
    lastmod: str = "",
    changefreq: str = "",
    priority: str = "",
) -> None:
    url_el = ET.SubElement(urlset, f"{{{SITEMAP_NS}}}url")
    ET.SubElement(url_el, f"{{{SITEMAP_NS}}}loc").text = f"{base}{path}"
    if lastmod:
        ET.SubElement(url_el, f"{{{SITEMAP_NS}}}lastmod").text = lastmod
    if changefreq:
        ET.SubElement(url_el, f"{{{SITEMAP_NS}}}changefreq").text = changefreq
    if priority:
        ET.SubElement(url_el, f"{{{SITEMAP_NS}}}priority").text = priority


def build_sitemap_xml() -> str:
    base = sitemap_base_url()
    today = timezone.localdate().isoformat()
    urlset = ET.Element(f"{{{SITEMAP_NS}}}urlset")

    for path in STATIC_PATHS:
        priority = "1.0" if path == "/" else "0.8"
        changefreq = "daily" if path == "/" else "weekly"
        _append_url(
            urlset,
            base,
            path,
            lastmod=today,
            changefreq=changefreq,
            priority=priority,
        )

    for path in CATEGORY_PATHS:
        _append_url(
            urlset,
            base,
            path,
            lastmod=today,
            changefreq="daily",
            priority="0.9",
        )

    equipment_qs = (
        Equipment.objects.visible()
        .only("pk", "created_at", "last_bumped_at")
        .order_by("-pk")
        .iterator(chunk_size=500)
    )
    for item in equipment_qs:
        lastmod_dt = item.last_bumped_at or item.created_at
        _append_url(
            urlset,
            base,
            f"/equipment/{item.pk}/",
            lastmod=_format_lastmod(lastmod_dt),
            changefreq="weekly",
            priority="0.7",
        )

    xml_body = ET.tostring(urlset, encoding="unicode")
    body = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_body}\n'
    _validate_sitemap_xml(body)
    return body


def _validate_sitemap_xml(body: str) -> None:
    lowered = body.lower()
    if "<script" in lowered or "</script" in lowered:
        raise ValueError("sitemap XML must not contain script tags")
    ET.fromstring(body)


def sitemap_xml(request):
    body = cache.get(SITEMAP_CACHE_KEY)
    if body is None:
        body = build_sitemap_xml()
        cache.set(SITEMAP_CACHE_KEY, body, timeout=SITEMAP_CACHE_SECONDS)
    else:
        try:
            _validate_sitemap_xml(body)
        except (ValueError, ET.ParseError):
            body = build_sitemap_xml()
            cache.set(SITEMAP_CACHE_KEY, body, timeout=SITEMAP_CACHE_SECONDS)

    response = HttpResponse(body, content_type="application/xml; charset=utf-8")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = f"public, max-age={SITEMAP_CACHE_SECONDS}"
    return response
