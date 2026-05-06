import mimetypes
import os
import zipfile
import io
from uuid import UUID

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, FileResponse, JsonResponse
from django.db.models import Q, Sum
from django.utils import timezone
from django.core.paginator import Paginator

from .models import Folder, File


@login_required
def file_list(request):
    folder_id = request.GET.get('folder', '')
    folder = None
    ancestors = []

    if folder_id:
        try:
            folder = Folder.objects.get(id=UUID(folder_id), owner=request.user, is_deleted=False)
            ancestors = folder.get_ancestors()
        except (Folder.DoesNotExist, ValueError):
            messages.error(request, '文件夹不存在')
            return redirect('file_list')

    # 子文件夹
    folders = Folder.objects.filter(owner=request.user, parent=folder, is_deleted=False)
    # 文件
    files_qs = File.objects.filter(owner=request.user, folder=folder, is_deleted=False)

    # 搜索
    search = request.GET.get('q', '').strip()
    if search:
        folders = folders.filter(name__icontains=search)
        files_qs = files_qs.filter(name__icontains=search)

    # 排序
    sort = request.GET.get('sort', '-created_at')
    sort_map = {
        'name': 'name',
        '-name': '-name',
        'size': 'size',
        '-size': '-size',
        'modified': 'updated_at',
        '-modified': '-updated_at',
        'created': 'created_at',
        '-created': '-created_at',
    }
    sort_field = sort_map.get(sort, '-created_at')
    if sort_field in ['name', '-name']:
        folders = folders.order_by(sort_field)
    files_qs = files_qs.order_by(sort_field)

    # 分页
    paginator = Paginator(files_qs, 50)
    page_num = request.GET.get('page', 1)
    files_page = paginator.get_page(page_num)

    # 左侧文件夹树
    folder_tree = _build_folder_tree(request.user)

    ctx = {
        'folder': folder,
        'ancestors': ancestors,
        'folders': folders,
        'files_page': files_page,
        'search': search,
        'sort': sort,
        'folder_tree': folder_tree,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'files/_file_list_content.html', ctx)
    return render(request, 'files/file_list.html', ctx)


def _build_folder_tree(user):
    """构建用户文件夹树"""
    all_folders = list(Folder.objects.filter(owner=user, is_deleted=False).values('id', 'name', 'parent_id'))
    return _build_tree(all_folders, None)


def _build_tree(folders, parent_id):
    return [
        {
            'id': f['id'],
            'name': f['name'],
            'children': _build_tree(folders, f['id']),
        }
        for f in folders if f['parent_id'] == parent_id
    ]


@login_required
def folder_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        parent_id = request.POST.get('parent', '') or None

        if not name:
            messages.error(request, '文件夹名不能为空')
            return redirect('file_list')

        parent = None
        if parent_id:
            try:
                parent = Folder.objects.get(id=UUID(parent_id), owner=request.user, is_deleted=False)
            except (Folder.DoesNotExist, ValueError):
                messages.error(request, '父文件夹不存在')
                return redirect('file_list')

        # 检测同名
        if Folder.objects.filter(owner=request.user, parent=parent, name=name, is_deleted=False).exists():
            messages.error(request, f'文件夹 "{name}" 已存在')
        else:
            Folder.objects.create(name=name, parent=parent, owner=request.user)

    return redirect(request.META.get('HTTP_REFERER', 'file_list'))


@login_required
def folder_rename(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id, owner=request.user, is_deleted=False)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            # 检测同名
            if Folder.objects.filter(owner=request.user, parent=folder.parent,
                                     name=name, is_deleted=False).exclude(pk=folder.pk).exists():
                return HttpResponse(f'文件夹 "{name}" 已存在', status=400)
            folder.name = name
            folder.save(update_fields=['name', 'updated_at'])
            return HttpResponse(status=204, headers={'HX-Trigger': 'refreshList'})

    return render(request, 'files/folder_rename.html', {'folder': folder})


@login_required
def folder_delete(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id, owner=request.user, is_deleted=False)

    if request.method == 'POST':
        _cancel_folder_shares(folder)
        folder.soft_delete()
        _recalc_storage(request.user)
        messages.success(request, f'文件夹 "{folder.name}" 已移至回收站')
        redirect_url = reverse('file_list')
        if folder.parent and not folder.parent.is_deleted:
            redirect_url = f"{reverse('file_list')}?folder={folder.parent.id}"
        resp = HttpResponse(status=204, headers={'HX-Redirect': redirect_url})
        return resp

    return render(request, 'files/folder_delete_confirm.html', {'folder': folder})


def _cancel_folder_shares(folder):
    """递归取消文件夹及其所有子文件和子目录的分享链接"""
    from sharing.models import ShareLink
    # 收集所有子文件ID
    file_ids = _collect_folder_file_ids(folder)
    # 收集所有子目录ID
    folder_ids = _collect_subfolder_ids(folder)
    ShareLink.objects.filter(file_id__in=file_ids).delete()
    ShareLink.objects.filter(folder_id__in=folder_ids).delete()


def _collect_folder_file_ids(folder):
    """递归收集文件夹下所有文件的ID"""
    ids = list(File.objects.filter(folder=folder).values_list('id', flat=True))
    for child in Folder.objects.filter(parent=folder):
        ids.extend(_collect_folder_file_ids(child))
    return ids


def _collect_subfolder_ids(folder):
    """递归收集文件夹下所有子文件夹的ID"""
    ids = [folder.id]
    for child in Folder.objects.filter(parent=folder):
        ids.extend(_collect_subfolder_ids(child))
    return ids


@login_required
def file_upload(request):
    if request.method == 'POST':
        folder_id = request.POST.get('folder', '') or None
        folder = None
        if folder_id:
            try:
                folder = Folder.objects.get(id=UUID(folder_id), owner=request.user, is_deleted=False)
            except (Folder.DoesNotExist, ValueError):
                return JsonResponse({'error': '文件夹不存在'}, status=400)

        uploaded_files = request.FILES.getlist('files')
        if not uploaded_files:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': '未选择文件'}, status=400)
            messages.error(request, '未选择文件')
            return redirect(request.META.get('HTTP_REFERER', 'file_list'))

        # 检查同名冲突
        new_names = [f.name for f in uploaded_files]
        existing = set(File.objects.filter(
            owner=request.user, folder=folder, is_deleted=False, name__in=new_names
        ).values_list('name', flat=True))
        conflicts = [n for n in new_names if n in existing]

        # 如果有冲突且未提供解决方案，返回冲突列表
        resolve_mode = request.POST.get('_resolve_mode', '')
        if conflicts and resolve_mode != 'resolved':
            return JsonResponse({'conflicts': conflicts, 'status': 'conflict'}, status=409)

        created = 0
        overwritten = 0
        skipped = 0
        for f in uploaded_files:
            if f.name in existing and resolve_mode == 'resolved':
                action = request.POST.get(f'_action_{f.name}', 'skip')
                if action == 'skip':
                    skipped += 1
                    continue
                elif action == 'overwrite':
                    old = File.objects.get(owner=request.user, folder=folder, name=f.name, is_deleted=False)
                    old.file.delete(save=False)
                    old.delete()
                    overwritten += 1
                elif action == 'rename':
                    base, ext = os.path.splitext(f.name)
                    counter = 1
                    new_name = f'{base} ({counter}){ext}'
                    while File.objects.filter(owner=request.user, folder=folder, name=new_name, is_deleted=False).exists():
                        counter += 1
                        new_name = f'{base} ({counter}){ext}'
                    f.name = new_name

            mime_type, _ = mimetypes.guess_type(f.name)
            mime_type = mime_type or 'application/octet-stream'
            try:
                File.objects.create(
                    name=f.name, file=f, size=f.size,
                    mime_type=mime_type, folder=folder, owner=request.user,
                )
                created += 1
            except Exception:
                skipped += 1

        _recalc_storage(request.user)

        msg_parts = [f'上传 {created} 个文件']
        if overwritten:
            msg_parts.append(f'覆盖 {overwritten} 个')
        if skipped:
            msg_parts.append(f'跳过 {skipped} 个')
        messages.success(request, '，'.join(msg_parts))

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'created': created, 'overwritten': overwritten, 'skipped': skipped, 'status': 'ok'})

        if request.headers.get('HX-Request'):
            resp = HttpResponse(status=204)
            resp['HX-Trigger'] = 'refreshList'
            return resp

        return redirect(request.META.get('HTTP_REFERER', 'file_list'))

    return HttpResponse(status=405)


@login_required
def file_download(request, file_id):
    file_obj = get_object_or_404(File, id=file_id, owner=request.user, is_deleted=False)
    response = FileResponse(file_obj.file, as_attachment=True, filename=file_obj.name)
    return response


@login_required
def file_preview(request, file_id):
    file_obj = get_object_or_404(File, id=file_id, owner=request.user, is_deleted=False)
    ctx = {'file': file_obj}

    if file_obj.is_image:
        ctx['preview_type'] = 'image'
    elif file_obj.is_text:
        ctx['preview_type'] = 'text'
        try:
            with open(file_obj.file.path, 'r', encoding='utf-8') as f:
                ctx['content'] = f.read(50000)
        except Exception as e:
            ctx['content'] = f'[读取错误: {type(e).__name__} — {e}]'
    elif file_obj.is_pdf:
        ctx['preview_type'] = 'pdf'
    else:
        ctx['preview_type'] = 'unsupported'

    if request.headers.get('HX-Request'):
        return render(request, 'files/_preview_inline.html', ctx)
    return render(request, 'files/preview.html', ctx)


@login_required
def file_edit(request, file_id):
    """Markdown 编辑器 — GET 加载内容，POST 保存"""
    file_obj = get_object_or_404(File, id=file_id, owner=request.user, is_deleted=False)

    if request.method == 'POST':
        new_content = request.POST.get('content', '')
        # 写入文件
        with open(file_obj.file.path, 'w', encoding='utf-8', newline='') as f:
            f.write(new_content)
        # 更新文件大小
        file_obj.size = len(new_content.encode('utf-8'))
        file_obj.save(update_fields=['size', 'updated_at'])
        _recalc_storage(request.user)
        messages.success(request, f'"{file_obj.name}" 已保存')
        redirect_url = reverse('file_list')
        if file_obj.folder and not file_obj.folder.is_deleted:
            redirect_url += f'?folder={file_obj.folder.id}'
        return redirect(redirect_url)

    try:
        with open(file_obj.file.path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        content = ''

    return render(request, 'files/markdown_edit.html', {
        'file': file_obj,
        'content': content,
    })


@login_required
def file_rename(request, file_id):
    file_obj = get_object_or_404(File, id=file_id, owner=request.user, is_deleted=False)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            file_obj.name = name
            file_obj.save(update_fields=['name', 'updated_at'])
            return HttpResponse(status=204, headers={'HX-Trigger': 'refreshList'})

    return render(request, 'files/file_rename.html', {'file': file_obj})


@login_required
def file_delete(request, file_id):
    file_obj = get_object_or_404(File, id=file_id, owner=request.user, is_deleted=False)

    if request.method == 'POST':
        file_obj.soft_delete()
        _recalc_storage(request.user)
        messages.success(request, f'文件 "{file_obj.name}" 已移至回收站')
        redirect_url = reverse('file_list')
        if file_obj.folder and not file_obj.folder.is_deleted:
            redirect_url = f"{reverse('file_list')}?folder={file_obj.folder.id}"
        resp = HttpResponse(status=204, headers={'HX-Redirect': redirect_url})
        return resp

    return render(request, 'files/file_delete_confirm.html', {'file': file_obj})


@login_required
def file_move(request, file_id):
    file_obj = get_object_or_404(File, id=file_id, owner=request.user, is_deleted=False)

    if request.method == 'POST':
        target_id = request.POST.get('target_folder', '') or None
        if target_id:
            try:
                target = Folder.objects.get(id=UUID(target_id), owner=request.user, is_deleted=False)
                file_obj.folder = target
                file_obj.save(update_fields=['folder', 'updated_at'])
            except (Folder.DoesNotExist, ValueError):
                return JsonResponse({'error': '目标文件夹不存在'}, status=400)
        else:
            file_obj.folder = None
            file_obj.save(update_fields=['folder', 'updated_at'])
        return HttpResponse(status=204, headers={'HX-Trigger': 'refreshList'})

    # GET: 显示文件夹选择器
    all_folders = _get_folder_choices(request.user)
    return render(request, 'files/file_move.html', {'file': file_obj, 'all_folders': all_folders})


def _get_folder_choices(user, parent_id=None, level=0):
    """获取扁平化的文件夹列表用于移动选择"""
    result = []
    folders = Folder.objects.filter(owner=user, parent_id=parent_id, is_deleted=False)
    for f in folders:
        result.append((f.id, '  ' * level + f.name))
        result.extend(_get_folder_choices(user, f.id, level + 1))
    return result


def _parse_id_list(post_data, key):
    """解析逗号分隔的 ID 字符串列表，过滤空值"""
    raw = post_data.get(key, '')
    return [x for x in raw.split(',') if x.strip()]


@login_required
def batch_delete(request):
    if request.method == 'POST':
        file_ids = _parse_id_list(request.POST, 'file_ids')
        folder_ids = _parse_id_list(request.POST, 'folder_ids')
        count = 0

        for fid in file_ids:
            try:
                f = File.objects.get(id=UUID(fid), owner=request.user, is_deleted=False)
                f.soft_delete()
                count += 1
            except (File.DoesNotExist, ValueError):
                pass

        for fid in folder_ids:
            try:
                f = Folder.objects.get(id=UUID(fid), owner=request.user, is_deleted=False)
                f.soft_delete()
                count += 1
            except (Folder.DoesNotExist, ValueError):
                pass

        _recalc_storage(request.user)
        messages.success(request, f'已将 {count} 个项目移至回收站')
        return HttpResponse(status=204, headers={'HX-Trigger': 'refreshList'})

    return HttpResponse(status=405)


@login_required
def batch_move(request):
    if request.method == 'POST':
        file_ids = _parse_id_list(request.POST, 'file_ids')
        target_id = request.POST.get('target_folder', '') or None
        target = None

        if target_id:
            try:
                target = Folder.objects.get(id=UUID(target_id), owner=request.user, is_deleted=False)
            except (Folder.DoesNotExist, ValueError):
                return JsonResponse({'error': '目标文件夹不存在'}, status=400)

        count = 0
        for fid in file_ids:
            try:
                f = File.objects.get(id=UUID(fid), owner=request.user, is_deleted=False)
                f.folder = target
                f.save(update_fields=['folder', 'updated_at'])
                count += 1
            except (File.DoesNotExist, ValueError):
                pass

        messages.success(request, f'已移动 {count} 个文件')
        return HttpResponse(status=204, headers={'HX-Trigger': 'refreshList'})

    return HttpResponse(status=405)


@login_required
def batch_download(request):
    if request.method == 'POST':
        file_ids = _parse_id_list(request.POST, 'file_ids')
        if not file_ids:
            messages.error(request, '未选择文件')
            return redirect('file_list')

        files_qs = File.objects.filter(id__in=file_ids, owner=request.user, is_deleted=False)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in files_qs:
                zf.write(f.file.path, f.name)

        buf.seek(0)
        response = HttpResponse(buf, content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="download.zip"'
        return response

    return HttpResponse(status=405)


@login_required
def folder_download(request, folder_id):
    """下载整个目录为 zip 包"""
    folder = get_object_or_404(Folder, id=folder_id, owner=request.user, is_deleted=False)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        _add_folder_to_zip(zf, folder, '')

    buf.seek(0)
    response = HttpResponse(buf, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{folder.name}.zip"'
    return response


def _add_folder_to_zip(zf, folder, prefix):
    """递归将文件夹内容加入 zip"""
    for f in File.objects.filter(folder=folder, is_deleted=False):
        zf.write(f.file.path, prefix + f.name)
    for child in Folder.objects.filter(parent=folder, is_deleted=False):
        _add_folder_to_zip(zf, child, prefix + child.name + '/')


# ── 回收站 ──

@login_required
def trash_list(request):
    # 只显示顶层已删除的文件夹（父目录未被删除的）和孤儿文件（所在文件夹未被删除的）
    top_folders = Folder.objects.filter(
        owner=request.user, is_deleted=True
    ).exclude(
        parent__is_deleted=True
    ).order_by('-deleted_at')

    # 孤儿文件：直接在根目录下或所在文件夹未被删除
    orphan_files = File.objects.filter(
        owner=request.user, is_deleted=True
    ).exclude(
        folder__is_deleted=True
    ).order_by('-deleted_at')

    ctx = {
        'deleted_folders': top_folders[:100],
        'deleted_files': orphan_files[:100],
    }
    return render(request, 'files/trash.html', ctx)


@login_required
def trash_folder_detail(request, folder_id):
    """浏览回收站中某个已删除文件夹的内容"""
    folder = get_object_or_404(Folder, id=folder_id, owner=request.user, is_deleted=True)
    sub_folders = Folder.objects.filter(parent=folder, is_deleted=True)
    sub_files = File.objects.filter(folder=folder, is_deleted=True)

    return render(request, 'files/trash_folder.html', {
        'folder': folder,
        'sub_folders': sub_folders,
        'sub_files': sub_files,
    })


@login_required
def trash_restore(request, item_type, item_id):
    if request.method != 'POST':
        return HttpResponse(status=405)

    if item_type == 'file':
        obj = get_object_or_404(File, id=item_id, owner=request.user, is_deleted=True)
        _restore_file_with_parents(obj)
    else:
        obj = get_object_or_404(Folder, id=item_id, owner=request.user, is_deleted=True)
        _restore_folder(obj)
        # 如果父目录不存在或也被删除，先恢复/重建父目录
        if obj.parent and obj.parent.is_deleted:
            _restore_folder(obj.parent)
        elif obj.parent is None:
            pass  # root folder, no parent needed

    _recalc_storage(request.user)
    messages.success(request, f'"{obj.name}" 已恢复')
    return redirect('trash')


def _restore_file_with_parents(file_obj):
    """恢复文件，智能处理父目录和同名冲突"""
    folder = file_obj.folder
    if folder and folder.is_deleted:
        _restore_folder(folder)

    # 检查目标位置是否有同名文件
    target_folder = file_obj.folder
    existing = File.objects.filter(
        owner=file_obj.owner, folder=target_folder, name=file_obj.name, is_deleted=False
    ).first()
    if existing:
        # 重命名恢复的文件
        base, ext = os.path.splitext(file_obj.name)
        counter = 1
        while File.objects.filter(
            owner=file_obj.owner, folder=target_folder,
            name=f'{base} ({counter}){ext}', is_deleted=False
        ).exists():
            counter += 1
        file_obj.name = f'{base} ({counter}){ext}'

    file_obj.is_deleted = False
    file_obj.deleted_at = None
    file_obj.save(update_fields=['is_deleted', 'deleted_at', 'name'])


def _restore_folder(folder):
    """递归恢复文件夹，如果目标位置已存在同名文件夹则智能合并内容"""
    # 先恢复父目录链
    if folder.parent and folder.parent.is_deleted:
        _restore_folder(folder.parent)

    # 检查目标位置是否已存在同名非删除文件夹
    existing = Folder.objects.filter(
        owner=folder.owner, parent=folder.parent,
        name=folder.name, is_deleted=False
    ).exclude(pk=folder.pk).first()

    if existing:
        # 合并：将所有子内容移到已存在的文件夹中
        _merge_folder_contents(folder, existing)
        # 删除旧的已删目录记录
        folder.delete()
    else:
        # 正常恢复
        folder.is_deleted = False
        folder.deleted_at = None
        folder.save(update_fields=['is_deleted', 'deleted_at'])
        for child in Folder.objects.filter(parent=folder, is_deleted=True):
            _restore_folder(child)
        for f in File.objects.filter(folder=folder, is_deleted=True):
            _restore_file_with_parents(f)


def _merge_folder_contents(source, target):
    """将 source 目录中的内容合并到 target 目录"""
    # 合并子目录
    for child in Folder.objects.filter(parent=source, is_deleted=True):
        child.parent = target
        child.save(update_fields=['parent'])
        _restore_folder(child)

    # 合并文件
    for f in File.objects.filter(folder=source, is_deleted=True):
        f.folder = target
        f.save(update_fields=['folder'])
        _restore_file_with_parents(f)

    # 处理未删除的子内容（不太可能但以防万一）
    for child in Folder.objects.filter(parent=source, is_deleted=False):
        child.parent = target
        child.save(update_fields=['parent'])
    for f in File.objects.filter(folder=source, is_deleted=False):
        f.folder = target
        f.save(update_fields=['folder'])


@login_required
def trash_destroy(request, item_type, item_id):
    if request.method != 'POST':
        return HttpResponse(status=405)

    if item_type == 'file':
        obj = get_object_or_404(File, id=item_id, owner=request.user, is_deleted=True)
        file_path = obj.file.path if obj.file else None
        obj.delete()
        if file_path:
            try:
                os.remove(file_path)
            except OSError:
                pass
    else:
        obj = get_object_or_404(Folder, id=item_id, owner=request.user, is_deleted=True)
        _destroy_folder(obj)

    _recalc_storage(request.user)
    messages.success(request, '已彻底删除')
    return redirect('trash')


def _destroy_folder(folder):
    for child in Folder.objects.filter(parent=folder, is_deleted=True):
        _destroy_folder(child)
    for f in File.objects.filter(folder=folder, is_deleted=True):
        f.file.delete(save=False)
        f.delete()
    folder.delete()


# ── 工具函数 ──

def _recalc_storage(user):
    total = File.objects.filter(owner=user, is_deleted=False).aggregate(s=Sum('size'))['s'] or 0
    # Include bucket file sizes
    from buckets.models import BucketFile
    bucket_total = BucketFile.objects.filter(bucket__owner=user).aggregate(s=Sum('size'))['s'] or 0
    from accounts.models import User
    User.objects.filter(pk=user.pk).update(storage_used=total + bucket_total)
