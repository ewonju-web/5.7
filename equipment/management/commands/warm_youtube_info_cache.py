# -*- coding: utf-8 -*-
"""중장비 유튜브(/info/) 분야별 YouTube 검색 결과 캐시 워밍."""
from django.core.management.base import BaseCommand

from equipment.youtube_info_service import (
    CATEGORY_TABS,
    _cache_key,
    fetch_youtube_videos,
)


class Command(BaseCommand):
    help = "정비유튜브 7개 분야 YouTube 검색 결과를 미리 캐시합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="기존 캐시를 지우고 YouTube API로 다시 조회합니다.",
        )
        parser.add_argument(
            "--category",
            type=str,
            default="",
            help="특정 분야만 워밍 (예: excavator_loading)",
        )

    def handle(self, *args, **options):
        from django.core.cache import cache

        refresh = options["refresh"]
        only = (options["category"] or "").strip().lower()
        targets = [
            (key, label)
            for key, label in CATEGORY_TABS
            if not only or key == only
        ]
        if only and not targets:
            self.stderr.write(self.style.ERROR(f"알 수 없는 분야: {only}"))
            return

        total = 0
        for key, label in targets:
            if refresh:
                cache.delete(_cache_key(key))
            items = fetch_youtube_videos(key, allow_api=True)
            count = len(items)
            total += count
            self.stdout.write(f"{label} ({key}): {count}건")

        self.stdout.write(self.style.SUCCESS(f"완료 — 총 {total}건 캐시"))
