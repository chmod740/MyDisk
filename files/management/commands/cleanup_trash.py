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
        for f in files:
            f.file.delete(save=False)
            f.delete()

        folders = Folder.objects.filter(is_deleted=True, deleted_at__lt=cutoff)
        folder_count = folders.count()
        for folder in folders:
            self._destroy_folder(folder)

        self.stdout.write(self.style.SUCCESS(
            f'清理完成: 删除了 {file_count} 个文件, {folder_count} 个文件夹'
        ))

    def _destroy_folder(self, folder):
        for child in Folder.objects.filter(parent=folder, is_deleted=True):
            self._destroy_folder(child)
        for f in File.objects.filter(folder=folder, is_deleted=True):
            f.file.delete(save=False)
            f.delete()
        folder.delete()
