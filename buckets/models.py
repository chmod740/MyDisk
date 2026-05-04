import uuid
import os
import secrets
from django.db import models
from django.conf import settings
from django.contrib.auth.hashers import make_password


def bucket_file_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f'bucket_files/{instance.bucket_id}/{instance.id}{ext}'


class Bucket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name='桶名称')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='buckets', verbose_name='所有者')
    is_public = models.BooleanField(default=False, verbose_name='公开访问')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '存储桶'
        verbose_name_plural = '存储桶'
        ordering = ['-created_at']
        unique_together = [('owner', 'name')]

    def __str__(self):
        return f'{self.owner.username}/{self.name}'

    @property
    def file_count(self):
        return self.files.count()

    @property
    def total_size(self):
        return self.files.aggregate(s=models.Sum('size'))['s'] or 0


class BucketFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bucket = models.ForeignKey(Bucket, on_delete=models.CASCADE,
                               related_name='files', verbose_name='所属桶')
    name = models.CharField(max_length=255, verbose_name='文件名')
    folder_path = models.CharField(max_length=500, default='', blank=True, verbose_name='目录路径')
    file = models.FileField(upload_to=bucket_file_upload_to, verbose_name='文件')
    size = models.BigIntegerField(default=0, verbose_name='文件大小(bytes)')
    mime_type = models.CharField(max_length=255, default='application/octet-stream',
                                 verbose_name='MIME类型')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '桶文件'
        verbose_name_plural = '桶文件'
        ordering = ['-created_at']
        unique_together = [('bucket', 'folder_path', 'name')]

    def __str__(self):
        return f'{self.bucket.name}/{self.name}'

    @property
    def extension(self):
        return os.path.splitext(self.name)[1].lower()

    @property
    def is_image(self):
        return self.mime_type.startswith('image/')

    @property
    def is_text(self):
        code_exts = {'.py', '.js', '.html', '.css', '.json', '.xml', '.md',
                     '.yml', '.yaml', '.sh', '.java', '.c', '.cpp', '.go', '.rs', '.ts', '.tsx'}
        return self.mime_type.startswith('text/') or self.extension in code_exts


class ApiKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='api_keys', verbose_name='用户')
    name = models.CharField(max_length=255, verbose_name='密钥名称')
    key_hash = models.CharField(max_length=128, verbose_name='密钥哈希')
    prefix = models.CharField(max_length=8, verbose_name='密钥前缀')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    last_accessed_at = models.DateTimeField(null=True, blank=True, verbose_name='上次访问时间')

    class Meta:
        verbose_name = 'API密钥'
        verbose_name_plural = 'API密钥'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username}/{self.name} ({self.prefix}...)'

    @classmethod
    def generate_key(cls):
        raw = 'djd_' + secrets.token_urlsafe(32)
        return raw, make_password(raw), raw[:8]

    @classmethod
    def verify_key(cls, raw_key):
        prefix = raw_key[:8]
        for candidate in cls.objects.filter(prefix=prefix, is_active=True).select_related('user'):
            from django.contrib.auth.hashers import check_password
            if check_password(raw_key, candidate.key_hash):
                return candidate
        return None
