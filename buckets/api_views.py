"""Bucket API — 通过 X-Api-Key 认证"""
import mimetypes
import os

from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .api_auth import api_key_required
from .models import Bucket, BucketFile


def _bucket_json(b):
    return {
        'id': str(b.id), 'name': b.name, 'is_public': b.is_public,
        'file_count': b.file_count, 'total_size': b.total_size,
        'created_at': b.created_at.isoformat(),
    }


# ── Bucket CRUD ──

@csrf_exempt
@api_key_required
def api_bucket_list(request):
    """GET /api/buckets/ — 列出用户的所有桶"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    buckets = Bucket.objects.filter(owner=request.user).order_by('-created_at')
    return JsonResponse({'buckets': [_bucket_json(b) for b in buckets]})


@csrf_exempt
@api_key_required
def api_bucket_create(request):
    """POST /api/buckets/create/ — 创建桶"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST

    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'name is required'}, status=400)
    if Bucket.objects.filter(owner=request.user, name=name).exists():
        return JsonResponse({'error': f'Bucket "{name}" already exists'}, status=409)

    is_public = data.get('is_public') in (True, 'true', 'True', '1', 'on')
    b = Bucket.objects.create(name=name, owner=request.user, is_public=is_public)
    return JsonResponse(_bucket_json(b), status=201)


@csrf_exempt
@api_key_required
def api_bucket_delete(request, pk):
    """DELETE /api/buckets/<id>/ — 删除桶"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        b = Bucket.objects.get(pk=pk, owner=request.user)
    except Bucket.DoesNotExist:
        return JsonResponse({'error': 'Bucket not found'}, status=404)

    name = b.name
    b.delete()
    return JsonResponse({'deleted': name})


# ── Bucket File CRUD ──

def _file_json(f):
    return {
        'id': str(f.id), 'name': f.name, 'size': f.size,
        'mime_type': f.mime_type, 'folder_path': f.folder_path,
        'created_at': f.created_at.isoformat(),
    }


@csrf_exempt
@api_key_required
def api_bucket_file_list(request, pk):
    """GET /api/buckets/<id>/files/ — 列出桶内文件"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        b = Bucket.objects.get(pk=pk, owner=request.user)
    except Bucket.DoesNotExist:
        return JsonResponse({'error': 'Bucket not found'}, status=404)

    path = request.GET.get('path', '').strip()
    if path and not path.endswith('/'):
        path += '/'
    files = BucketFile.objects.filter(bucket=b, folder_path=path).exclude(name='.keep').order_by('-created_at')

    # 子目录
    all_paths = BucketFile.objects.filter(bucket=b).values_list('folder_path', flat=True).distinct()
    subfolders = set()
    plen = len(path)
    for p in all_paths:
        if p.startswith(path) and p != path:
            rest = p[plen:]
            seg = rest.split('/')[0]
            if seg:
                subfolders.add(seg)

    return JsonResponse({
        'bucket': _bucket_json(b),
        'current_path': path,
        'subfolders': sorted(subfolders),
        'files': [_file_json(f) for f in files],
    })


@csrf_exempt
@api_key_required
def api_bucket_file_upload(request, pk):
    """POST /api/buckets/<id>/upload/ — 上传文件到桶"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        b = Bucket.objects.get(pk=pk, owner=request.user)
    except Bucket.DoesNotExist:
        return JsonResponse({'error': 'Bucket not found'}, status=404)

    uploaded_files = request.FILES.getlist('files')
    folder_path = request.POST.get('folder_path', '').strip()
    if folder_path and not folder_path.endswith('/'):
        folder_path += '/'

    if not uploaded_files:
        return JsonResponse({'error': 'No files provided'}, status=400)

    created = []
    for f in uploaded_files:
        if f.name == '.keep':
            continue
        mime_type, _ = mimetypes.guess_type(f.name)
        try:
            bf = BucketFile.objects.create(
                bucket=b, name=f.name, file=f, size=f.size,
                mime_type=mime_type or 'application/octet-stream',
                folder_path=folder_path,
            )
            created.append(_file_json(bf))
        except Exception as e:
            created.append({'name': f.name, 'error': str(e)})

    return JsonResponse({'created': created, 'count': len([x for x in created if 'id' in x])}, status=201)


@csrf_exempt
@api_key_required
def api_bucket_file_delete(request, pk, file_id):
    """DELETE /api/buckets/<id>/files/<fid>/ — 删除桶内文件"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        b = Bucket.objects.get(pk=pk, owner=request.user)
    except Bucket.DoesNotExist:
        return JsonResponse({'error': 'Bucket not found'}, status=404)

    try:
        bf = BucketFile.objects.get(pk=file_id, bucket=b)
    except BucketFile.DoesNotExist:
        return JsonResponse({'error': 'File not found'}, status=404)

    name = bf.name
    bf.file.delete(save=False)
    bf.delete()
    return JsonResponse({'deleted': name})


# ── Bucket Folder ──

@csrf_exempt
@api_key_required
def api_bucket_folder_create(request, pk):
    """POST /api/buckets/<id>/folder/create/ — 创建目录"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        b = Bucket.objects.get(pk=pk, owner=request.user)
    except Bucket.DoesNotExist:
        return JsonResponse({'error': 'Bucket not found'}, status=404)

    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST

    folder_name = (data.get('name') or '').strip()
    parent_path = (data.get('parent_path') or '').strip()

    if not folder_name:
        return JsonResponse({'error': 'name is required'}, status=400)

    full_path = (parent_path.rstrip('/') + '/' if parent_path else '') + folder_name + '/'

    if BucketFile.objects.filter(bucket=b, folder_path=full_path, name='.keep').exists():
        return JsonResponse({'error': f'Folder "{folder_name}" already exists'}, status=409)

    from django.core.files.uploadedfile import SimpleUploadedFile
    placeholder = SimpleUploadedFile('.keep', b'.', content_type='application/x-directory')
    BucketFile.objects.create(
        bucket=b, name='.keep', folder_path=full_path,
        file=placeholder, size=1, mime_type='application/x-directory',
    )
    return JsonResponse({'created': folder_name, 'path': full_path}, status=201)


@csrf_exempt
@api_key_required
def api_bucket_folder_delete(request, pk):
    """DELETE /api/buckets/<id>/folder/ — 删除目录（通过 ?path= 参数）"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        b = Bucket.objects.get(pk=pk, owner=request.user)
    except Bucket.DoesNotExist:
        return JsonResponse({'error': 'Bucket not found'}, status=404)

    path = request.GET.get('path', '').strip()
    if not path:
        return JsonResponse({'error': 'path parameter is required'}, status=400)
    if not path.endswith('/'):
        path += '/'

    count = 0
    for bf in BucketFile.objects.filter(bucket=b, folder_path__startswith=path):
        bf.file.delete(save=False)
        bf.delete()
        count += 1

    return JsonResponse({'deleted': count, 'path': path})
