import uuid
from django.db import models
from django.conf import settings


class ShareLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey('files.File', on_delete=models.CASCADE, null=True, blank=True,
                             related_name='share_links', verbose_name='分享文件')
    folder = models.ForeignKey('files.Folder', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='share_links', verbose_name='分享文件夹')
    bucket = models.ForeignKey('buckets.Bucket', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='share_links', verbose_name='分享桶')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='share_links', verbose_name='分享者')
    password = models.CharField(max_length=128, null=True, blank=True, verbose_name='访问密码')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='过期时间')
    view_count = models.IntegerField(default=0, verbose_name='浏览次数')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '分享链接'
        verbose_name_plural = '分享链接'
        ordering = ['-created_at']

    def __str__(self):
        target = self.file or self.folder or self.bucket
        return f'分享: {target}'

    @property
    def target(self):
        return self.file or self.folder or self.bucket

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at
