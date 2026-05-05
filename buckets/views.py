import mimetypes
import os
from uuid import UUID

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, FileResponse, JsonResponse
from django.utils import timezone

from .models import Bucket, BucketFile, ApiKey


def _check_access(request, bucket):
    """检查桶的访问权限。返回 (can_access, reason)"""
    if bucket.is_public:
        return True, None
    if not request.user.is_authenticated:
        return False, 'auth_required'
    if request.user != bucket.owner:
        return False, 'forbidden'
    return True, None


# ── Bucket CRUD ──

@login_required
def bucket_list(request):
    buckets = Bucket.objects.filter(owner=request.user).prefetch_related('files')
    return render(request, 'buckets/list.html', {'buckets': buckets})


@login_required
def bucket_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        is_public = request.POST.get('is_public') == 'on'

        if not name:
            messages.error(request, '桶名称不能为空')
            return render(request, 'buckets/list.html', {'buckets': Bucket.objects.filter(owner=request.user)})

        if Bucket.objects.filter(owner=request.user, name=name).exists():
            messages.error(request, f'桶 "{name}" 已存在')
            return render(request, 'buckets/list.html', {'buckets': Bucket.objects.filter(owner=request.user)})

        Bucket.objects.create(name=name, owner=request.user, is_public=is_public)
        messages.success(request, f'桶 "{name}" 创建成功')
        return redirect('bucket_list')

    return redirect('bucket_list')


def bucket_detail(request, pk):
    bucket = get_object_or_404(Bucket, pk=pk)
    can_access, reason = _check_access(request, bucket)

    if reason == 'auth_required':
        return redirect(f'/accounts/login/?next=/buckets/{pk}/')
    if reason == 'forbidden':
        messages.error(request, '无权访问此桶')
        return redirect('bucket_list')

    # 当前浏览的目录路径
    current_path = request.GET.get('path', '').strip()
    if current_path and not current_path.endswith('/'):
        current_path += '/'

    # 当前目录中的文件
    files = bucket.files.filter(folder_path=current_path).order_by('-created_at')

    # 子目录（从所有文件的路径中提取，在当前层级下）
    all_paths = bucket.files.values_list('folder_path', flat=True).distinct()
    subfolders = set()
    prefix_len = len(current_path)
    for p in all_paths:
        if p.startswith(current_path) and p != current_path:
            rest = p[prefix_len:]
            seg = rest.split('/')[0]
            if seg:
                subfolders.add(seg)

    # 面包屑
    breadcrumbs = []
    if current_path:
        parts = current_path.rstrip('/').split('/')
        accumulated = ''
        for part in parts:
            accumulated += part + '/'
            breadcrumbs.append({'name': part, 'path': accumulated})

    is_owner = request.user.is_authenticated and request.user == bucket.owner

    # 构建桶内文件夹树
    bucket_folder_tree = _build_bucket_folder_tree(bucket)

    return render(request, 'buckets/detail.html', {
        'bucket': bucket,
        'files': files,
        'current_path': current_path,
        'subfolders': sorted(subfolders),
        'breadcrumbs': breadcrumbs,
        'is_owner': is_owner,
        'folder_tree': bucket_folder_tree,
        'folder': {'id': current_path} if current_path else None,
        'tree_link_prefix': f'/buckets/{pk}',
    })


def _build_bucket_folder_tree(bucket):
    """从桶文件的 folder_path 构建文件夹树"""
    paths = bucket.files.values_list('folder_path', flat=True).distinct()
    tree = {}
    for p in paths:
        if not p:
            continue
        parts = p.rstrip('/').split('/')
        current = tree
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]
    return _dict_to_tree(tree)


def _dict_to_tree(d, parent_path=''):
    """将嵌套字典转为 _tree_node.html 期望的格式"""
    result = []
    for name, children in sorted(d.items()):
        node = {
            'id': parent_path + name + '/',
            'name': name,
            'children': _dict_to_tree(children, parent_path + name + '/'),
        }
        result.append(node)
    return result


@login_required
def bucket_delete(request, pk):
    bucket = get_object_or_404(Bucket, pk=pk, owner=request.user)
    if request.method == 'POST':
        name = bucket.name
        bucket.delete()
        messages.success(request, f'桶 "{name}" 已删除')
        return redirect('bucket_list')
    return redirect('bucket_detail', pk=pk)


@login_required
def bucket_folder_create(request, pk):
    """在桶中创建目录"""
    bucket = get_object_or_404(Bucket, pk=pk, owner=request.user)
    if request.method == 'POST':
        folder_name = request.POST.get('name', '').strip()
        parent_path = request.POST.get('parent_path', '').strip()
        if not folder_name:
            messages.error(request, '目录名不能为空')
        else:
            full_path = (parent_path.rstrip('/') + '/' if parent_path else '') + folder_name + '/'
            # 检测同名目录
            if BucketFile.objects.filter(bucket=bucket, folder_path=full_path, name='.keep').exists():
                messages.error(request, f'目录 "{folder_name}" 已存在')
            else:
                from django.core.files.uploadedfile import SimpleUploadedFile
                placeholder = SimpleUploadedFile('.keep', b'.', content_type='application/x-directory')
                BucketFile.objects.create(
                    bucket=bucket, name='.keep',
                    folder_path=full_path, file=placeholder,
                    size=1, mime_type='application/x-directory',
                )
                messages.success(request, f'目录 "{folder_name}" 创建成功')
        redirect_url = f'/buckets/{pk}/'
        if parent_path:
            redirect_url += f'?path={parent_path}'
        return redirect(redirect_url)
    return redirect('bucket_detail', pk=pk)


# ── Bucket File Operations ──

@login_required
def bucket_file_upload(request, pk):
    bucket = get_object_or_404(Bucket, pk=pk, owner=request.user)

    if request.method == 'POST':
        uploaded_files = request.FILES.getlist('files')
        folder_path = request.POST.get('folder_path', '').strip()
        if folder_path and not folder_path.endswith('/'):
            folder_path += '/'

        if not uploaded_files:
            messages.error(request, '未选择文件')
            return redirect(f'/buckets/{pk}/')

        # 过滤掉 .keep 文件
        real_files = [f for f in uploaded_files if f.name != '.keep']
        if not real_files:
            return JsonResponse({'created': 0, 'status': 'ok'})

        # 检查同名冲突
        new_names = [f.name for f in real_files]
        existing = set(BucketFile.objects.filter(
            bucket=bucket, folder_path=folder_path, name__in=new_names
        ).values_list('name', flat=True))
        conflicts = [n for n in new_names if n in existing]

        resolve_mode = request.POST.get('_resolve_mode', '')
        if conflicts and resolve_mode != 'resolved':
            return JsonResponse({'conflicts': conflicts, 'status': 'conflict'}, status=409)

        created = 0
        overwritten = 0
        skipped = 0
        for f in real_files:
            if f.name in existing and resolve_mode == 'resolved':
                action = request.POST.get(f'_action_{f.name}', 'skip')
                if action == 'skip':
                    skipped += 1
                    continue
                elif action == 'overwrite':
                    old = BucketFile.objects.get(bucket=bucket, folder_path=folder_path, name=f.name)
                    old.file.delete(save=False)
                    old.delete()
                    overwritten += 1
                elif action == 'rename':
                    base, ext = os.path.splitext(f.name)
                    counter = 1
                    new_name = f'{base} ({counter}){ext}'
                    while BucketFile.objects.filter(bucket=bucket, folder_path=folder_path, name=new_name).exists():
                        counter += 1
                        new_name = f'{base} ({counter}){ext}'
                    f.name = new_name

            mime_type, _ = mimetypes.guess_type(f.name)
            try:
                BucketFile.objects.create(
                    bucket=bucket, name=f.name, file=f,
                    size=f.size, mime_type=mime_type or 'application/octet-stream',
                    folder_path=folder_path,
                )
                created += 1
            except Exception:
                skipped += 1

        msg_parts = [f'上传 {created} 个']
        if overwritten:
            msg_parts.append(f'覆盖 {overwritten} 个')
        if skipped:
            msg_parts.append(f'跳过 {skipped} 个')
        messages.success(request, '，'.join(msg_parts))

        redirect_url = f'/buckets/{pk}/'
        if folder_path:
            redirect_url += f'?path={folder_path}'
        return redirect(redirect_url)

    return HttpResponse(status=405)


def bucket_file_download(request, pk, file_id):
    bucket = get_object_or_404(Bucket, pk=pk)
    can_access, reason = _check_access(request, bucket)

    if reason == 'auth_required':
        return redirect(f'/accounts/login/?next=/buckets/{pk}/files/{file_id}/download/')
    if reason == 'forbidden':
        return HttpResponse('Forbidden', status=403)

    file_obj = get_object_or_404(BucketFile, pk=file_id, bucket=bucket)
    return FileResponse(file_obj.file, as_attachment=True, filename=file_obj.name)


@login_required
def bucket_file_delete(request, pk, file_id):
    bucket = get_object_or_404(Bucket, pk=pk, owner=request.user)
    file_obj = get_object_or_404(BucketFile, pk=file_id, bucket=bucket)

    if request.method == 'POST':
        name = file_obj.name
        file_obj.file.delete(save=False)
        file_obj.delete()
        messages.success(request, f'文件 "{name}" 已删除')
        return redirect('bucket_detail', pk=pk)

    return redirect('bucket_detail', pk=pk)


@login_required
def bucket_file_rename(request, pk, file_id):
    """重命名桶内文件，检测同名冲突"""
    bucket = get_object_or_404(Bucket, pk=pk, owner=request.user)
    file_obj = get_object_or_404(BucketFile, pk=file_id, bucket=bucket)

    if request.method == 'POST':
        new_name = request.POST.get('name', '').strip()
        if not new_name:
            return HttpResponse('文件名不能为空', status=400)
        if BucketFile.objects.filter(bucket=bucket, folder_path=file_obj.folder_path,
                                     name=new_name).exclude(pk=file_obj.pk).exists():
            return HttpResponse(f'文件 "{new_name}" 已存在', status=409)
        file_obj.name = new_name
        file_obj.save(update_fields=['name'])
        return HttpResponse(status=204)

    return HttpResponse(status=405)


@login_required
def bucket_folder_rename(request, pk):
    """重命名桶内目录——更新该目录下所有文件的 folder_path"""
    bucket = get_object_or_404(Bucket, pk=pk, owner=request.user)

    if request.method == 'POST':
        old_path = request.POST.get('old_path', '').strip()
        new_name = request.POST.get('new_name', '').strip()
        parent_path = request.POST.get('parent_path', '').strip()

        if not old_path or not new_name:
            messages.error(request, '参数不完整')
            return redirect('bucket_detail', pk=pk)

        new_path = (parent_path.rstrip('/') + '/' if parent_path else '') + new_name + '/'

        # 检测同名
        if BucketFile.objects.filter(bucket=bucket, folder_path=new_path, name='.keep').exists():
            messages.error(request, f'目录 "{new_name}" 已存在')
            return redirect(f'/buckets/{pk}/?path={parent_path}')

        # 更新该目录下所有文件的 folder_path
        count = 0
        for f in BucketFile.objects.filter(bucket=bucket, folder_path=old_path):
            f.folder_path = new_path
            f.save(update_fields=['folder_path'])
            count += 1

        # 同时更新子目录
        for f in BucketFile.objects.filter(bucket=bucket, folder_path__startswith=old_path):
            if f.folder_path == old_path:
                continue  # already updated
            f.folder_path = new_path + f.folder_path[len(old_path):]
            f.save(update_fields=['folder_path'])
            count += 1

        messages.success(request, f'目录已重命名为 "{new_name}"（{count} 个项目已更新）')
        return redirect(f'/buckets/{pk}/?path={parent_path}')

    return HttpResponse(status=405)


def bucket_folder_download(request, pk):
    """下载桶内目录为 zip 包（公开桶无需登录）"""
    bucket = get_object_or_404(Bucket, pk=pk)
    can_access, reason = _check_access(request, bucket)
    if not can_access:
        return HttpResponse('Forbidden', status=403)

    path = request.GET.get('path', '').strip()
    if path and not path.endswith('/'):
        path += '/'

    files = BucketFile.objects.filter(bucket=bucket, folder_path__startswith=path).exclude(name='.keep')
    if not files:
        return HttpResponse('No files', status=404)

    import io as _io, zipfile as _zipfile
    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, 'w', _zipfile.ZIP_DEFLATED) as zf:
        plen = len(path)
        for f in files:
            arcname = f.folder_path[plen:] + f.name if f.folder_path.startswith(path) else f.name
            zf.write(f.file.path, arcname)

    buf.seek(0)
    folder_name = path.rstrip('/').split('/')[-1] if path.rstrip('/') else bucket.name
    resp = HttpResponse(buf, content_type='application/zip')
    resp['Content-Disposition'] = f'attachment; filename="{folder_name}.zip"'
    return resp


# ── API Key Management ──

@login_required
def api_key_list(request):
    keys = ApiKey.objects.filter(user=request.user)
    resp = render(request, 'buckets/api_keys.html', {'keys': keys})
    # 清除一次性显示的 API key
    request.session.pop('api_key_raw', None)
    request.session.pop('api_key_name', None)
    return resp


@login_required
def api_key_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, '密钥名称不能为空')
            return redirect('api_key_list')

        raw, hashed, prefix = ApiKey.generate_key()
        key = ApiKey.objects.create(
            user=request.user, name=name,
            key_hash=hashed, prefix=prefix,
        )

        # 只在创建成功的响应中显示原始密钥
        request.session['api_key_raw'] = raw
        request.session['api_key_name'] = name
        messages.success(request, 'API Key 创建成功（仅显示一次）')
        return redirect('api_key_list')

    return redirect('api_key_list')


@login_required
def api_key_revoke(request, pk):
    key = get_object_or_404(ApiKey, pk=pk, user=request.user)
    if request.method == 'POST':
        key.is_active = False
        key.save(update_fields=['is_active'])
        messages.success(request, f'API Key "{key.name}" 已撤销')
    return redirect('api_key_list')


@login_required
def api_key_delete(request, pk):
    key = get_object_or_404(ApiKey, pk=pk, user=request.user)
    if request.method == 'POST':
        name = key.name
        key.delete()
        messages.success(request, f'API Key "{name}" 已删除')
    return redirect('api_key_list')


# ── API Endpoint ──

def api_bucket_file_download(request, pk, file_id):
    """通过 X-Api-Key header 下载私有桶文件"""
    api_key = request.headers.get('X-Api-Key', '')
    if not api_key:
        return HttpResponse('Missing X-Api-Key header', status=401)

    key_obj = ApiKey.verify_key(api_key)
    if not key_obj:
        return HttpResponse('Invalid or inactive API key', status=403)

    bucket = get_object_or_404(Bucket, pk=pk)

    # API key 只能访问自己所有的桶
    if bucket.owner_id != key_obj.user_id:
        return HttpResponse('Forbidden: bucket not owned by key owner', status=403)

    # 更新最后访问时间
    ApiKey.objects.filter(pk=key_obj.pk).update(last_accessed_at=timezone.now())

    file_obj = get_object_or_404(BucketFile, pk=file_id, bucket=bucket)
    return FileResponse(file_obj.file, as_attachment=True, filename=file_obj.name)


def bucket_file_download_url(request, pk, file_id):
    """返回带token的下载URL（私有桶需要）"""
    bucket = get_object_or_404(Bucket, pk=pk)
    can_access, reason = _check_access(request, bucket)
    if not can_access:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    file_obj = get_object_or_404(BucketFile, pk=file_id, bucket=bucket)

    file_path = (file_obj.folder_path + file_obj.name).strip('/')
    base = request.build_absolute_uri('/')[:-1]
    url = f'{base}/buckets/{bucket.id}/dl/{file_path}'

    if not bucket.is_public:
        token = _generate_download_token(bucket, file_obj)
        url += f'?token={token}'

    return JsonResponse({'url': url, 'filename': file_obj.name})


def bucket_file_preview(request, pk, file_id):
    """桶文件预览"""
    bucket = get_object_or_404(Bucket, pk=pk)
    can_access, reason = _check_access(request, bucket)
    if not can_access:
        if reason == 'auth_required':
            return redirect(f'/accounts/login/?next=/buckets/{pk}/files/{file_id}/preview/')
        return HttpResponse('Forbidden', status=403)

    file_obj = get_object_or_404(BucketFile, pk=file_id, bucket=bucket)
    ctx = {'file': file_obj, 'bucket': bucket}

    if file_obj.is_image:
        ctx['preview_type'] = 'image'
    elif file_obj.is_text:
        ctx['preview_type'] = 'text'
        try:
            with file_obj.file.open('r') as f:
                ctx['content'] = f.read(50000)
        except Exception:
            ctx['content'] = '[无法读取文件内容]'
    elif file_obj.mime_type == 'application/pdf':
        ctx['preview_type'] = 'pdf'
    else:
        ctx['preview_type'] = 'unsupported'

    if request.headers.get('HX-Request'):
        return render(request, 'buckets/_preview_inline.html', ctx)
    return render(request, 'buckets/preview.html', ctx)


# ── 路径风格下载 ──

def bucket_file_download_path(request, pk, file_path):
    """通过路径风格URL下载文件: /buckets/<id>/dl/<path>/<filename>
    私有桶支持 ?token=<signed_token> 鉴权"""
    bucket = get_object_or_404(Bucket, pk=pk)

    # 解析路径
    file_path = file_path.strip('/')
    parts = file_path.split('/')
    filename = parts[-1]
    folder = '/'.join(parts[:-1]) + '/' if len(parts) > 1 else ''

    # 鉴权
    if not bucket.is_public:
        token = request.GET.get('token', '')
        if token:
            from django.core.signing import Signer, BadSignature
            signer = Signer(salt='bucket_dl')
            try:
                unsigned = signer.unsign(token)
                # token格式: bucket_id:file_path:timestamp
                expected = f'{str(bucket.id)}:{file_path}'
                if unsigned.rsplit(':', 1)[0] != expected:
                    return HttpResponse('Invalid token', status=403)
                # 检查时间戳（1小时有效）
                import time
                ts = int(unsigned.rsplit(':', 1)[1])
                if int(time.time()) - ts > 3600:
                    return HttpResponse('Token expired', status=403)
            except BadSignature:
                return HttpResponse('Invalid token', status=403)
        else:
            can_access, reason = _check_access(request, bucket)
            if not can_access:
                if reason == 'auth_required':
                    return redirect(f'/accounts/login/?next={request.path}')
                return HttpResponse('Forbidden', status=403)
    else:
        # 公开桶，检查token存在性（仅限通过session认证）
        pass

    file_obj = get_object_or_404(BucketFile, bucket=bucket, folder_path=folder, name=filename)
    return FileResponse(file_obj.file, as_attachment=True, filename=file_obj.name)


def _generate_download_token(bucket, file_obj):
    """为私有桶文件生成1小时有效的下载token"""
    from django.core.signing import Signer
    import time
    signer = Signer(salt='bucket_dl')
    file_path = (file_obj.folder_path + file_obj.name).strip('/')
    value = f'{str(bucket.id)}:{file_path}:{int(time.time())}'
    return signer.sign(value)


# ── API 文档 ──

@login_required
def api_docs(request):
    sample_key = ApiKey.objects.filter(user=request.user, is_active=True).first()
    sample_bucket = Bucket.objects.filter(owner=request.user).first()
    sample_file = BucketFile.objects.filter(bucket__owner=request.user).first()

    return render(request, 'buckets/api_docs.html', {
        'sample_key': sample_key,
        'sample_bucket': sample_bucket,
        'sample_file': sample_file,
        'base_url': request.build_absolute_uri('/')[:-1],
    })
