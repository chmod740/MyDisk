from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from files.models import File, Folder


class Command(BaseCommand):
    help = '清理回收站中超过30天的文件和文件夹'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=30)

        files = File.objects.filter(is_deleted=True, deleted_at__lt=cutoff)
        file_count = files.count()
        files.delete()

        folders = Folder.objects.filter(is_deleted=True, deleted_at__lt=cutoff)
        folder_count = folders.count()
        folders.delete()

        self.stdout.write(self.style.SUCCESS(
            f'清理完成: 删除了 {file_count} 个文件, {folder_count} 个文件夹'
        ))
