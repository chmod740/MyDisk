from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from accounts.models import User
from .models import File


def _counted_size(instance):
    return 0 if instance.is_deleted else instance.size


@receiver(pre_save, sender=File)
def file_pre_save(sender, instance, **kwargs):
    previous = 0
    instance._previous_file = None
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).only('size', 'is_deleted', 'file').first()
        if old:
            previous = _counted_size(old)
            if old.file.name and old.file.name != instance.file.name:
                instance._previous_file = (old.file.storage, old.file.name)
    instance._previous_counted_size = previous


@receiver(post_save, sender=File)
def file_post_save(sender, instance, **kwargs):
    previous = getattr(instance, '_previous_counted_size', 0)
    delta = _counted_size(instance) - previous
    if delta:
        User.objects.filter(pk=instance.owner_id).update(
            storage_used=F('storage_used') + delta,
        )
    previous_file = getattr(instance, '_previous_file', None)
    if previous_file and not getattr(instance, '_replacement_cleanup_managed', False):
        storage, name = previous_file
        transaction.on_commit(lambda: storage.delete(name))


@receiver(post_delete, sender=File)
def file_post_delete(sender, instance, **kwargs):
    counted_size = _counted_size(instance)
    if counted_size:
        User.objects.filter(pk=instance.owner_id).update(
            storage_used=F('storage_used') - counted_size,
        )

    storage = instance.file.storage
    name = instance.file.name
    if name:
        transaction.on_commit(lambda: storage.delete(name))
