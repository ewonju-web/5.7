"""SQLi·봇 공격으로 오염된 사용자 콘텐츠 일괄 삭제·계정 차단."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q

from chat.models import ChatMessage
from equipment.content_security import ban_user_account, block_ip, text_has_attack_payload
from equipment.models import (
    Comment,
    DriverProfile,
    Equipment,
    ExamComment,
    ExamPost,
    FinanceConsultation,
    JobPost,
    Part,
    PartsShop,
)
from soil.models import SoilPost
from trust.models import SellerReport, SellerReview

User = get_user_model()


def _q_attack(*field_names):
    q = Q()
    for name in field_names:
        q |= Q(**{f'{name}__icontains': 'sleep('})
        q |= Q(**{f'{name}__icontains': 'pg_sleep'})
        q |= Q(**{f'{name}__icontains': 'XOR('})
        q |= Q(**{f'{name}__icontains': 'union select'})
        q |= Q(**{f'{name}__icontains': '-1 OR'})
        q |= Q(**{f'{name}__icontains': '%2527'})
        q |= Q(**{f'{name}__icontains': '@@'})
        q |= Q(**{f'{name}__iregex': r"'\s*or\s+"})
    return q


def _purge_queryset(qs, fields, label, dry_run):
    ids = []
    authors = set()
    for obj in qs.iterator(chunk_size=500):
        values = [getattr(obj, f, '') for f in fields]
        if text_has_attack_payload(*[str(v) for v in values]):
            ids.append(obj.pk)
            author = getattr(obj, 'author', None) or getattr(obj, 'sender', None) or getattr(obj, 'reporter', None)
            if author and author.pk:
                authors.add(author.pk)
    if dry_run:
        return len(ids), authors
    if ids:
        deleted, _ = qs.model.objects.filter(pk__in=ids).delete()
        return deleted, authors
    return 0, authors


class Command(BaseCommand):
    help = 'SQLi·봇 공격 콘텐츠 검색·삭제 및 작성자/IP 차단'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='삭제 없이 건수만 출력')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        total_deleted = 0
        author_ids = set()

        targets = [
            (ExamPost.objects.all(), ('title', 'content', 'youtube_url'), 'ExamPost'),
            (ExamComment.objects.all(), ('content',), 'ExamComment'),
            (JobPost.objects.all(), ('title', 'content', 'location', 'contact', 'company_name'), 'JobPost'),
            (SoilPost.objects.all(), ('title', 'location', 'contact', 'description', 'note', 'quantity'), 'SoilPost'),
            (Equipment.objects.all(), ('model_name', 'manufacturer', 'description', 'current_location'), 'Equipment'),
            (Part.objects.all(), ('title', 'description', 'location', 'contact'), 'Part'),
            (Comment.objects.all(), ('content', 'author_name'), 'Comment'),
            (ChatMessage.objects.all(), ('message',), 'ChatMessage'),
            (FinanceConsultation.objects.all(), ('applicant_name', 'contact', 'memo', 'desired_equipment'), 'FinanceConsultation'),
            (PartsShop.objects.all(), ('name', 'region', 'address', 'contact', 'note'), 'PartsShop'),
            (DriverProfile.objects.all(), ('name', 'region', 'contact', 'description', 'address'), 'DriverProfile'),
            (SellerReview.objects.all(), ('comment',), 'SellerReview'),
            (SellerReport.objects.all(), ('detail',), 'SellerReport'),
        ]

        for qs, fields, label in targets:
            # 1차 DB 필터로 후보 축소
            narrowed = qs.filter(_q_attack(*fields))
            deleted, authors = _purge_queryset(narrowed, fields, label, dry_run)
            total_deleted += deleted
            author_ids |= authors
            self.stdout.write(f'{label}: {deleted}건 {"(dry-run)" if dry_run else "삭제"}')

        # fnfOzvSR 등 알려진 공격 계정 강제 포함
        from equipment.bot_blocklist import find_bot_user_queryset

        known = find_bot_user_queryset().values_list('pk', flat=True)
        author_ids |= set(known)

        if not dry_run:
            for uid in sorted(author_ids):
                user = User.objects.filter(pk=uid).first()
                if user and user.is_active:
                    ban_user_account(user)
                    self.stdout.write(self.style.WARNING(f'계정 차단: {user.username} (#{user.pk})'))

            from equipment.models import VisitPageLog

            blocked_ips = set()
            for uid in author_ids:
                ips = (
                    VisitPageLog.objects.filter(user_id=uid)
                    .values_list('ip_address', flat=True)
                    .distinct()
                )
                for ip in ips:
                    if ip and ip not in blocked_ips:
                        blocked_ips.add(ip)
                        block_ip(ip)
                        self.stdout.write(self.style.WARNING(f'IP 차단(캐시): {ip}'))

        self.stdout.write(self.style.SUCCESS(
            f'완료: 총 {total_deleted}건 처리, 작성자 {len(author_ids)}명'
        ))
