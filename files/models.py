import uuid
import os
from django.db import models
from django.conf import settings


def file_upload_to(instance, filename):
    from django.utils import timezone
    ext = os.path.splitext(filename)[1]
    user_id = instance.owner_id
    now = instance.created_at or timezone.now()
    return f'{user_id}/{now:%Y/%m}/{instance.id}{ext}'


class Folder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name='文件夹名')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='children', verbose_name='父文件夹')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='folders', verbose_name='所有者')
    is_deleted = models.BooleanField(default=False, verbose_name='已删除')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '文件夹'
        verbose_name_plural = '文件夹'
        ordering = ['name']
        indexes = [
            models.Index(fields=['owner', 'parent', 'is_deleted']),
        ]

    def __str__(self):
        return self.name

    def get_ancestors(self):
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return list(reversed(ancestors))

    def soft_delete(self):
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])
        for child in self.children.all():
            child.soft_delete()
        for f in self.files.all():
            f.soft_delete()


class File(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name='文件名')
    file = models.FileField(upload_to=file_upload_to, verbose_name='文件')
    size = models.BigIntegerField(default=0, verbose_name='文件大小(bytes)')
    mime_type = models.CharField(max_length=255, default='application/octet-stream', verbose_name='MIME类型')
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, null=True, blank=True,
                               related_name='files', verbose_name='所属文件夹')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='files', verbose_name='所有者')
    is_deleted = models.BooleanField(default=False, verbose_name='已删除')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '文件'
        verbose_name_plural = '文件'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'folder', 'is_deleted']),
        ]

    def __str__(self):
        return self.name

    @property
    def extension(self):
        return os.path.splitext(self.name)[1].lower()

    @property
    def is_image(self):
        return self.mime_type.startswith('image/')

    @property
    def is_text(self):
        return self.mime_type.startswith('text/') or self.extension in {
            '.py', '.js', '.html', '.css', '.json', '.xml', '.md',
            '.yml', '.yaml', '.ini', '.cfg', '.toml', '.sh', '.bat',
            '.java', '.c', '.cpp', '.h', '.rs', '.go', '.ts', '.tsx',
        }

    @property
    def is_pdf(self):
        return self.mime_type == 'application/pdf'

    def soft_delete(self):
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])
