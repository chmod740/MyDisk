from django.core.management.base import BaseCommand

from accounts.models import User
from files.services import recalculate_storage


class Command(BaseCommand):
    help = '重新计算用户的存储用量'

    def add_arguments(self, parser):
        parser.add_argument('--user', help='只重算指定用户名')

    def handle(self, *args, **options):
        users = User.objects.all()
        if options['user']:
            users = users.filter(username=options['user'])
            if not users.exists():
                self.stderr.write(self.style.ERROR('用户不存在'))
                return

        count = 0
        for user in users.iterator():
            total = recalculate_storage(user)
            self.stdout.write(f'{user.username}: {total} bytes')
            count += 1
        self.stdout.write(self.style.SUCCESS(f'已重算 {count} 个用户'))
