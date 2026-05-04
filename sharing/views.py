import io
import zipfile
from uuid import UUID

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, FileResponse
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password

from files.models import File, Folder
from buckets.models import Bucket, BucketFile
from .models import ShareLink


@login_required
def share_create(request):
    is_htmx = request.headers.get('HX-Request')

    if request.method == 'POST':
        file_id = request.POST.get('file_id', '') or None
        folder_id = request.POST.get('folder_id', '') or None
        bucket_id = request.POST.get('bucket_id', '') or None
        password = request.POST.get('password', '').strip() or None
        expires_days = request.POST.get('expires_days', '')

        target_file = None
        target_folder = None
        target_bucket = None

        if file_id:
            target_file = get_object_or_404(File, id=UUID(file_id), owner=request.user, is_deleted=False)
        elif folder_id:
            target_folder = get_object_or_404(Folder, id=UUID(folder_id), owner=request.user, is_deleted=False)
        elif bucket_id:
            target_bucket = get_object_or_404(Bucket, id=UUID(bucket_id), owner=request.user)
        else:
            messages.error(request, '请选择要分享的文件、文件夹或桶')
            if is_htmx:
                return render(request, 'sharing/_share_create_modal.html')
            return redirect('file_list')

        expires_at = None
        if expires_days:
            try:
                days = int(expires_days)
                if days > 0:
                    expires_at = timezone.now() + timezone.timedelta(days=days)
            except ValueError:
                pass

        link = ShareLink.objects.create(
            file=target_file,
            folder=target_folder,
            bucket=target_bucket,
            owner=request.user,
            password=make_password(password) if password else None,
            expires_at=expires_at,
        )

        messages.success(request, '分享链接已生成')

        share_url = request.build_absolute_uri(f'/share/{link.id}/')

        if is_htmx:
            return render(request, 'sharing/_share_success_modal.html', {
                'link': link, 'share_url': share_url, 'raw_password': password or '',
            })

        return redirect('share_manage')

    template = 'sharing/_share_create_modal.html' if is_htmx else 'sharing/share_create.html'
    return render(request, template)


@login_required
def share_manage(request):
    links = ShareLink.objects.filter(owner=request.user).select_related('file', 'folder', 'bucket')
    return render(request, 'sharing/share_manage.html', {'links': links})


@login_required
def share_delete(request, share_id):
    link = get_object_or_404(ShareLink, id=share_id, owner=request.user)
    if request.method == 'POST':
        link.delete()
        messages.success(request, '分享链接已删除')
        return redirect('share_manage')
    return render(request, 'sharing/share_delete_confirm.html', {'link': link})


def share_access(request, share_id):
    try:
        share_id = UUID(str(share_id))
        link = ShareLink.objects.select_related('file', 'folder', 'bucket').get(id=share_id)
    except (ValueError, ShareLink.DoesNotExist):
        return render(request, 'sharing/share_error.html', {'error': '分享链接无效或已删除'})

    if link.is_expired:
        return render(request, 'sharing/share_error.html', {'error': '分享链接已过期'})

    if link.password:
        if request.method == 'POST' and request.POST.get('password'):
            if check_password(request.POST['password'], link.password):
                request.session[f'share_auth_{link.id}'] = True
            else:
                return render(request, 'sharing/share_password.html', {'link': link, 'error': '密码错误'})
        elif not request.session.get(f'share_auth_{link.id}'):
            return render(request, 'sharing/share_password.html', {'link': link})

    link.view_count += 1
    link.save(update_fields=['view_count'])

    # 下载请求
    if request.GET.get('download') == '1' and link.file:
        return FileResponse(link.file.file, as_attachment=True, filename=link.file.name)

    # 下载分享文件夹中的单个文件
    file_download_id = request.GET.get('dl_file')
    if file_download_id and link.folder:
        try:
            f = File.objects.get(id=UUID(file_download_id), folder=link.folder, is_deleted=False)
            return FileResponse(f.file, as_attachment=True, filename=f.name)
        except (File.DoesNotExist, ValueError):
            return render(request, 'sharing/share_error.html', {'error': '文件不存在'})

    # 打包下载整个分享文件夹
    if request.GET.get('download') == 'zip' and link.folder:
        import io, zipfile
        files = File.objects.filter(folder=link.folder, is_deleted=False)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(f.file.path, f.name)
        buf.seek(0)
        resp = HttpResponse(buf, content_type='application/zip')
        resp['Content-Disposition'] = f'attachment; filename="{link.folder.name}.zip"'
        return resp

    if link.file:
        return render(request, 'sharing/share_file.html', {'link': link, 'file': link.file})
    elif link.folder:
        files = File.objects.filter(folder=link.folder, is_deleted=False)
        subfolders = Folder.objects.filter(parent=link.folder, is_deleted=False)
        return render(request, 'sharing/share_folder.html', {
            'link': link, 'folder': link.folder,
            'files': files, 'subfolders': subfolders,
        })
    elif link.bucket:
        bucket_files = BucketFile.objects.filter(bucket=link.bucket).order_by('-created_at')
        return render(request, 'sharing/share_bucket.html', {
            'link': link, 'bucket': link.bucket, 'files': bucket_files,
        })

    return render(request, 'sharing/share_error.html', {'error': '分享内容不存在'})
