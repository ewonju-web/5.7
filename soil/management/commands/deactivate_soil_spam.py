# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from soil.models import SoilPost
from soil.antispam import is_obvious_soil_spam


class Command(BaseCommand):
    help = "봇 도배로 보이는 현장 자재 글을 비활성화(is_active=False)합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='비활성화 대상만 출력합니다.',
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get('dry_run'))
        qs = SoilPost.objects.filter(is_active=True)
        spam_posts = [p for p in qs if is_obvious_soil_spam(p)]
        self.stdout.write(f'비활성화 대상: {len(spam_posts)}건 / 활성 {qs.count()}건')

        for post in spam_posts[:15]:
            self.stdout.write(f'  - [{post.pk}] {post.title!r} / {post.location!r}')
        if len(spam_posts) > 15:
            self.stdout.write(f'  ... 외 {len(spam_posts) - 15}건')

        if dry_run:
            return

        updated = SoilPost.objects.filter(pk__in=[p.pk for p in spam_posts]).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f'비활성화 완료: {updated}건'))
