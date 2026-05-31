from django import template

register = template.Library()

GAUGE_CIRCUMFERENCE = 188.5


@register.filter
def manner_gauge_offset(score):
    """SVG 원형 게이지 stroke-dashoffset (0~100점)."""
    try:
        s = float(score or 0)
    except (TypeError, ValueError):
        s = 0.0
    s = max(0.0, min(100.0, s))
    return GAUGE_CIRCUMFERENCE - (GAUGE_CIRCUMFERENCE * s / 100.0)


@register.filter
def manner_gauge_color(score):
    try:
        s = float(score or 0)
    except (TypeError, ValueError):
        s = 0.0
    if s >= 90:
        return '#1D9E75'
    if s >= 70:
        return '#378ADD'
    if s >= 50:
        return '#EF9F27'
    return '#E24B4A'
