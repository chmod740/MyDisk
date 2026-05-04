from django.contrib.auth.models import AbstractUser
from django.db import models


class UserGroup(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    name = models.CharField(max_length=255, unique=True, verbose_name='组名称')
    storage_quota = models.BigIntegerField(default=1073741824, verbose_name='存储配额(bytes)')
    is_default = models.BooleanField(default=False, verbose_name='默认组')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '用户组'
        verbose_name_plural = '用户组'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            UserGroup.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        if not self.id:
            import uuid
            self.id = uuid.uuid4()
        super().save(*args, **kwargs)


class SiteSettings(models.Model):
    """单例模式站点设置"""
    site_name = models.CharField(max_length=100, default='DjangoDisk', verbose_name='网站名称')
    allow_registration = models.BooleanField(default=True, verbose_name='允许注册')
    require_captcha_register = models.BooleanField(default=False, verbose_name='注册需要验证码')
    require_captcha_login = models.BooleanField(default=False, verbose_name='登录需要验证码')
    default_storage_quota = models.BigIntegerField(default=1073741824, verbose_name='默认存储配额(bytes)')
    default_group = models.ForeignKey(UserGroup, on_delete=models.SET_NULL,
                                      null=True, blank=True, verbose_name='默认用户组')

    class Meta:
        verbose_name = '站点设置'
        verbose_name_plural = '站点设置'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class User(AbstractUser):
    storage_used = models.BigIntegerField(default=0, verbose_name='已用存储(bytes)')
    storage_quota = models.BigIntegerField(default=1073741824, verbose_name='存储配额(bytes)')
    group = models.ForeignKey(UserGroup, on_delete=models.SET_NULL,
                              null=True, blank=True, related_name='users', verbose_name='所属用户组')

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'
