"""Files API — 通过 X-Api-Key 认证"""
import mimetypes
import os
from uuid import UUID

from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt

from buckets.api_auth import api_key_required
from .models import Folder, File


def _file_json(f):
    return {
        'id': str(f.id), 'name': f.name, 'size': f.size,
        'mime_type': f.mime_type, 'folder_id': str(f.folder_id) if f.folder_id else None,
        'created_at': f.created_at.isoformat(),
    }


def _folder_json(d):
    return {
        'id': str(d.id), 'name': d.name,
        'parent_id': str(d.parent_id) if d.parent_id else None,
        'created_at': d.created_at.isoformat(),
    }


@csrf_exempt
@api_key_required
def api_file_list(request):
    """GET /api/files/ — 列出文件（可选 ?folder=<id>）"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    folder_id = request.GET.get('folder', '') or None
    folder = None
    if folder_id:
        try:
            folder = Folder.objects.get(id=UUID(folder_id), owner=request.user, is_deleted=False)
        except (Folder.DoesNotExist, ValueError):
            return JsonResponse({'error': 'Folder not found'}, status=404)

    folders = Folder.objects.filter(owner=request.user, parent=folder, is_deleted=False)
    files = File.objects.filter(owner=request.user, folder=folder, is_deleted=False).order_by('-created_at')

    return JsonResponse({
        'current_folder': _folder_json(folder) if folder else None,
        'folders': [_folder_json(d) for d in folders],
        'files': [_file_json(f) for f in files],
    })


@csrf_exempt
@api_key_required
def api_file_upload(request):
    """POST /api/files/upload/ — 上传文件（可选 folder=<id>）"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    folder_id = request.POST.get('folder', '') or None
    folder = None
    if folder_id:
        try:
            folder = Folder.objects.get(id=UUID(folder_id), owner=request.user, is_deleted=False)
        except (Folder.DoesNotExist, ValueError):
            return JsonResponse({'error': 'Folder not found'}, status=404)

    uploaded_files = request.FILES.getlist('files')
    if not uploaded_files:
        return JsonResponse({'error': 'No files provided'}, status=400)

    created = []
    for f in uploaded_files:
        mime_type, _ = mimetypes.guess_type(f.name)
        try:
            file_obj = File.objects.create(
                name=f.name, file=f, size=f.size,
                mime_type=mime_type or 'application/octet-stream',
                folder=folder, owner=request.user,
            )
            created.append(_file_json(file_obj))
        except Exception as e:
            created.append({'name': f.name, 'error': str(e)})

    return JsonResponse({'created': created}, status=201)


@csrf_exempt
@api_key_required
def api_file_download(request, file_id):
    """GET /api/files/<id>/download/ — 下载文件"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        f = File.objects.get(id=file_id, owner=request.user, is_deleted=False)
    except File.DoesNotExist:
        return JsonResponse({'error': 'File not found'}, status=404)

    return FileResponse(f.file, as_attachment=True, filename=f.name)


@csrf_exempt
@api_key_required
def api_file_delete(request, file_id):
    """DELETE /api/files/<id>/ — 软删除文件"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        f = File.objects.get(id=file_id, owner=request.user, is_deleted=False)
    except File.DoesNotExist:
        return JsonResponse({'error': 'File not found'}, status=404)

    name = f.name
    f.soft_delete()
    return JsonResponse({'deleted': name})


@csrf_exempt
@api_key_required
def api_folder_create(request):
    """POST /api/files/folder/create/ — 创建文件夹"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST

    name = (data.get('name') or '').strip()
    parent_id = (data.get('parent') or data.get('parent_id') or '').strip() or None

    if not name:
        return JsonResponse({'error': 'name is required'}, status=400)

    parent = None
    if parent_id:
        try:
            parent = Folder.objects.get(id=UUID(parent_id), owner=request.user, is_deleted=False)
        except (Folder.DoesNotExist, ValueError):
            return JsonResponse({'error': 'Parent folder not found'}, status=404)

    if Folder.objects.filter(owner=request.user, parent=parent, name=name, is_deleted=False).exists():
        return JsonResponse({'error': f'Folder "{name}" already exists'}, status=409)

    d = Folder.objects.create(name=name, parent=parent, owner=request.user)
    return JsonResponse(_folder_json(d), status=201)
