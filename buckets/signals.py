from django.db.models.signals import post_save, post_delete
from django.db.models import F
from django.dispatch import receiver
from .models import BucketFile


@receiver(post_save, sender=BucketFile)
def bucketfile_post_save(sender, instance, created, **kwargs):
    if created:
        from accounts.models import User
        User.objects.filter(pk=instance.bucket.owner_id).update(
            storage_used=F('storage_used') + instance.size
        )


@receiver(post_delete, sender=BucketFile)
def bucketfile_post_delete(sender, instance, **kwargs):
    from accounts.models import User
    User.objects.filter(pk=instance.bucket.owner_id).update(
        storage_used=F('storage_used') - instance.size
    )
