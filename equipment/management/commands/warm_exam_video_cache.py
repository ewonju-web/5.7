# -*- coding: utf-8 -*-
"""시험동영상(/jobs/exam/videos/) YouTube 검색 결과 캐시 워밍·메타데이터 채움.

업로드일·재생시간·조회수는 videos.list 로 보강되어 캐시에 함께 저장된다.
기존에 메타데이터 없이 캐시된 영상들을 한 번에 갱신할 때는 --refresh 와 함께 실행한다.
"""
from django.core.cache import cache
from django.core.management.base import BaseCommand

from equipment.exam_utils import EXAM_VIDEO_KEYWORD_MAP, fetch_exam_youtube_videos


class Command(BaseCommand):
    help = "시험동영상 분야별 YouTube 영상(업로드일·재생시간·조회수 포함)을 캐시에 채웁니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="기존 캐시를 삭제하고 메타데이터를 새로 가져옵니다.",
        )
        parser.add_argument(
            "--equipment",
            type=str,
            default="",
            help="특정 장비키만 갱신(excavator/forklift/crane/common). 비우면 전체.",
        )

    def handle(self, *args, **options):
        refresh = options["refresh"]
        only = (options["equipment"] or "").strip()

        if only:
            if only not in EXAM_VIDEO_KEYWORD_MAP:
                self.stderr.write(self.style.ERROR(f"알 수 없는 장비키: {only}"))
                return
            targets = [only]
        else:
            targets = list(EXAM_VIDEO_KEYWORD_MAP.keys())

        total = 0
        total_with_meta = 0
        for key in targets:
            label = key or "all"
            if refresh:
                cache.delete(f'youtube_api:exam:v5:{key or "all"}')
            items = fetch_exam_youtube_videos(key)
            with_meta = sum(
                1 for it in items if it.get("duration") or it.get("view_count")
            )
            total += len(items)
            total_with_meta += with_meta
            self.stdout.write(f"  [{label}] {len(items)}건 (메타데이터 {with_meta}건)")

        self.stdout.write(
            self.style.SUCCESS(
                f"완료 — 총 {total}건 캐시, 메타데이터 {total_with_meta}건"
            )
        )
