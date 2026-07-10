import os
import tempfile
import zipfile
from pathlib import PurePosixPath

from django.db import transaction
from django.db.models import Sum
from django.core.files.base import ContentFile
from django.http import FileResponse


class QuotaExceeded(ValueError):
    def __init__(self, used, quota, requested):
        self.used = used
        self.quota = quota
        self.requested = requested
        super().__init__('存储空间不足')


def calculate_storage_used(user):
    from buckets.models import BucketFile
    from files.models import File

    file_total = File.objects.filter(
        owner=user, is_deleted=False,
    ).aggregate(total=Sum('size'))['total'] or 0
    bucket_total = BucketFile.objects.filter(
        bucket__owner=user,
    ).exclude(name='.keep').aggregate(total=Sum('size'))['total'] or 0
    return file_total + bucket_total


def recalculate_storage(user):
    from accounts.models import User

    total = calculate_storage_used(user)
    User.objects.filter(pk=user.pk).update(storage_used=total)
    user.storage_used = total
    return total


def ensure_quota(user, additional_bytes):
    from accounts.models import User

    additional_bytes = max(0, int(additional_bytes or 0))
    locked_user = User.objects.select_for_update().get(pk=user.pk)
    used = calculate_storage_used(locked_user)
    if used + additional_bytes > locked_user.storage_quota:
        raise QuotaExceeded(used, locked_user.storage_quota, additional_bytes)
    return used


def replace_stored_file(instance, upload, **updated_fields):
    old_storage = instance.file.storage
    old_name = instance.file.name
    instance._replacement_cleanup_managed = True
    instance.file = upload
    for field, value in updated_fields.items():
        setattr(instance, field, value)

    update_fields = ['file', *updated_fields.keys()]
    try:
        instance.save(update_fields=update_fields)
    except Exception:
        del instance._replacement_cleanup_managed
        new_name = instance.file.name
        if new_name and new_name != old_name:
            instance.file.storage.delete(new_name)
        raise

    new_name = instance.file.name
    del instance._replacement_cleanup_managed
    if old_name and old_name != new_name:
        transaction.on_commit(lambda: old_storage.delete(old_name))
    return instance


def replace_text_content(instance, content):
    encoded = content.encode('utf-8')
    upload = ContentFile(encoded, name=instance.name)
    return replace_stored_file(instance, upload, size=len(encoded))


def validate_path_component(value, label='名称'):
    value = (value or '').strip()
    if not value:
        raise ValueError(f'{label}不能为空')
    if value in {'.', '..'} or '/' in value or '\\' in value:
        raise ValueError(f'{label}包含非法路径字符')
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f'{label}包含控制字符')
    return value


def normalize_bucket_path(value, allow_empty=True):
    value = (value or '').strip()
    if not value:
        if allow_empty:
            return ''
        raise ValueError('目录路径不能为空')
    if value.startswith(('/', '\\')) or '\\' in value:
        raise ValueError('目录路径必须是相对路径')

    raw_parts = value.rstrip('/').split('/')
    if any(not part for part in raw_parts):
        raise ValueError('目录路径包含空路径段')
    parts = [validate_path_component(part, '目录名') for part in raw_parts]
    return '/'.join(parts) + '/'


def safe_archive_name(value):
    value = (value or '').replace('\\', '/')
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts:
        raise ValueError('ZIP 路径必须是相对路径')
    parts = [validate_path_component(part, 'ZIP 路径') for part in path.parts]
    return '/'.join(parts)


def zip_file_response(entries, download_name):
    download_name = validate_path_component(download_name, '下载文件名')
    archive = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode='w+b')
    try:
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zf:
            for source_path, archive_name in entries:
                if not os.path.isfile(source_path):
                    continue
                zf.write(source_path, safe_archive_name(archive_name))
        archive.seek(0)
        return FileResponse(
            archive,
            as_attachment=True,
            filename=f'{download_name}.zip',
            content_type='application/zip',
        )
    except Exception:
        archive.close()
        raise


def folder_zip_entries(folder):
    from files.models import File, Folder

    all_folders = list(Folder.objects.filter(owner=folder.owner, is_deleted=False))
    children = {}
    for item in all_folders:
        children.setdefault(item.parent_id, []).append(item)

    folder_paths = {folder.id: ''}
    stack = [folder]
    while stack:
        current = stack.pop()
        for child in children.get(current.id, []):
            folder_paths[child.id] = (
                folder_paths[current.id]
                + validate_path_component(child.name, '文件夹名')
                + '/'
            )
            stack.append(child)

    files = File.objects.filter(
        owner=folder.owner, folder_id__in=folder_paths, is_deleted=False,
    )
    return [
        (
            item.file.path,
            folder_paths[item.folder_id] + validate_path_component(item.name, '文件名'),
        )
        for item in files
    ]
