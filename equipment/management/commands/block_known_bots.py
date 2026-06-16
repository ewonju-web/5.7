"""알려진 fnfOzvSR·555-666-0606 봇 계정·IP 일괄 차단."""
from django.core.management.base import BaseCommand

from equipment.bot_blocklist import purge_known_bots


class Command(BaseCommand):
    help = 'fnfOzvSR·555-666-0606 봇 계정 비활성화 및 IP 차단'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='차단 없이 대상만 출력')

    def handle(self, *args, **options):
        result = purge_known_bots(dry_run=options['dry_run'])
        mode = '(dry-run)' if options['dry_run'] else '차단'
        self.stdout.write(f'대상 계정 {result["users"]}명, IP {result["ips"]}개 {mode}')
        for name in result.get('usernames') or []:
            self.stdout.write(f'  - {name}')
        if not options['dry_run']:
            self.stdout.write(self.style.SUCCESS('봇 차단 완료'))
