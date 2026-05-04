"""Admin panel views for site settings, user/group management"""
from uuid import UUID

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Count

from .models import User, UserGroup, SiteSettings


@staff_member_required
def admin_settings(request):
    settings = SiteSettings.get_settings()
    groups = UserGroup.objects.all()

    if request.method == 'POST':
        settings.site_name = request.POST.get('site_name', 'DjangoDisk').strip() or 'DjangoDisk'
        try:
            settings.default_storage_quota = int(request.POST.get('default_storage_quota', '1073741824'))
        except (ValueError, TypeError):
            settings.default_storage_quota = 1073741824
        settings.allow_registration = request.POST.get('allow_registration') == 'on'
        settings.require_captcha_register = request.POST.get('require_captcha_register') == 'on'
        settings.require_captcha_login = request.POST.get('require_captcha_login') == 'on'

        default_group_id = request.POST.get('default_group') or None
        if default_group_id:
            try:
                settings.default_group = UserGroup.objects.get(id=UUID(default_group_id))
            except (UserGroup.DoesNotExist, ValueError):
                pass
        else:
            settings.default_group = None

        settings.save()
        messages.success(request, '站点设置已更新')

    return render(request, 'accounts/settings.html', {
        'settings': settings,
        'groups': groups,
    })


@staff_member_required
def admin_user_list(request):
    users = User.objects.select_related('group').annotate(
        file_count=Count('files', distinct=True)
    ).order_by('-date_joined')
    admin_count = User.objects.filter(is_superuser=True).count()
    return render(request, 'accounts/user_list.html', {
        'users': users,
        'admin_count': admin_count,
    })


@staff_member_required
def admin_user_update(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    groups = UserGroup.objects.all()

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'update_group':
            group_id = request.POST.get('group') or None
            if group_id:
                try:
                    group = UserGroup.objects.get(id=UUID(group_id))
                    user_obj.group = group
                    user_obj.storage_quota = group.storage_quota
                    user_obj.save(update_fields=['group', 'storage_quota'])
                    messages.success(request, f'已将 {user_obj.username} 移至组 {group.name}')
                except (UserGroup.DoesNotExist, ValueError):
                    messages.error(request, '无效的用户组')
            else:
                user_obj.group = None
                user_obj.save(update_fields=['group'])
                messages.success(request, f'已移除 {user_obj.username} 的用户组')

        elif action == 'change_password':
            new_pass = request.POST.get('new_password', '')
            if len(new_pass) < 6:
                messages.error(request, '密码长度至少6位')
            else:
                user_obj.set_password(new_pass)
                user_obj.save()
                messages.success(request, f'已修改 {user_obj.username} 的密码')

        elif action == 'toggle_admin':
            current_admin = user_obj.is_superuser
            if current_admin:
                admin_count = User.objects.filter(is_superuser=True).count()
                if admin_count <= 1:
                    messages.error(request, '无法移除最后一个管理员')
                else:
                    user_obj.is_staff = False
                    user_obj.is_superuser = False
                    user_obj.save()
                    messages.success(request, f'已移除 {user_obj.username} 的管理员权限')
            else:
                user_obj.is_staff = True
                user_obj.is_superuser = True
                user_obj.save()
                messages.success(request, f'已将 {user_obj.username} 设为管理员')

        return redirect('admin_user_list')


@staff_member_required
def admin_user_create(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        is_admin = request.POST.get('is_admin') == 'on'

        errors = []
        if not username:
            errors.append('用户名不能为空')
        if len(password) < 6:
            errors.append('密码长度至少6位')
        if User.objects.filter(username=username).exists():
            errors.append('用户名已存在')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            if is_admin:
                user.is_staff = True
                user.is_superuser = True
                user.save()
            messages.success(request, f'用户 "{username}" 创建成功')
            return redirect('admin_user_list')

    return render(request, 'accounts/user_create.html')

    return render(request, 'accounts/user_edit.html', {
        'user_obj': user_obj,
        'groups': groups,
    })


@staff_member_required
def admin_group_list(request):
    groups = UserGroup.objects.annotate(user_count=Count('users')).order_by('-is_default', 'name')
    return render(request, 'accounts/group_list.html', {'groups': groups})


@staff_member_required
def admin_group_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        quota = request.POST.get('quota', '')
        is_default = request.POST.get('is_default') == 'on'

        if not name:
            messages.error(request, '组名称不能为空')
            return render(request, 'accounts/group_form.html', {'group': None})

        try:
            quota_bytes = int(quota)
            if quota_bytes < 1:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, '请输入有效的配额数值')
            return render(request, 'accounts/group_form.html', {'group': None})

        if UserGroup.objects.filter(name=name).exists():
            messages.error(request, f'组 "{name}" 已存在')
            return render(request, 'accounts/group_form.html', {'group': None})

        UserGroup.objects.create(name=name, storage_quota=quota_bytes, is_default=is_default)
        messages.success(request, f'用户组 "{name}" 创建成功')
        return redirect('admin_group_list')

    return render(request, 'accounts/group_form.html', {'group': None})


@staff_member_required
def admin_group_edit(request, pk):
    group = get_object_or_404(UserGroup, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        quota = request.POST.get('quota', '')
        is_default = request.POST.get('is_default') == 'on'

        if not name:
            messages.error(request, '组名称不能为空')
            return render(request, 'accounts/group_form.html', {'group': group})

        try:
            quota_bytes = int(quota)
            if quota_bytes < 1:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, '请输入有效的配额数值')
            return render(request, 'accounts/group_form.html', {'group': group})

        if UserGroup.objects.filter(name=name).exclude(pk=group.pk).exists():
            messages.error(request, f'组 "{name}" 已存在')
            return render(request, 'accounts/group_form.html', {'group': group})

        old_quota = group.storage_quota
        group.name = name
        group.storage_quota = quota_bytes
        group.is_default = is_default
        group.save()

        if quota_bytes != old_quota:
            User.objects.filter(group=group).update(storage_quota=quota_bytes)

        messages.success(request, f'用户组 "{name}" 更新成功')
        return redirect('admin_group_list')

    return render(request, 'accounts/group_form.html', {'group': group})


@staff_member_required
def admin_group_delete(request, pk):
    group = get_object_or_404(UserGroup, pk=pk)
    user_count = group.users.count()

    if request.method == 'POST':
        if group.is_default:
            messages.error(request, '无法删除默认用户组，请先设置其他组为默认')
            return redirect('admin_group_list')

        group.users.update(group=None)
        name = group.name
        group.delete()
        messages.success(request, f'用户组 "{name}" 已删除')
        return redirect('admin_group_list')

    return render(request, 'accounts/group_delete_confirm.html', {
        'group': group,
        'user_count': user_count,
    })
@staff_member_required
def admin_user_list(request):
    users = User.objects.select_related('group').annotate(
        file_count=Count('files', distinct=True)
    ).order_by('-date_joined')

    # 检查当前请求用户是否是唯一的超级管理员
    admin_count = User.objects.filter(is_superuser=True).count()
    is_only_admin = request.user.is_superuser and admin_count <= 1

    return render(request, 'accounts/user_list.html', {
        'users': users,
        'is_only_admin': is_only_admin,
    })


@staff_member_required
def admin_user_update(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    groups = UserGroup.objects.all()

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'update_group':
            group_id = request.POST.get('group') or None
            if group_id:
                try:
                    group = UserGroup.objects.get(id=UUID(group_id))
                    user_obj.group = group
                    user_obj.storage_quota = group.storage_quota
                    user_obj.save(update_fields=['group', 'storage_quota'])
                    messages.success(request, f'已将 {user_obj.username} 移至组 {group.name}（配额: {group.storage_quota}）')
                except (UserGroup.DoesNotExist, ValueError):
                    messages.error(request, '无效的用户组')
            else:
                user_obj.group = None
                user_obj.save(update_fields=['group'])
                messages.success(request, f'已移除 {user_obj.username} 的用户组')

        elif action == 'toggle_admin':
            current_admin = user_obj.is_staff and user_obj.is_superuser
            if current_admin:
                # 不能移除最后一个管理员
                admin_count = User.objects.filter(is_superuser=True).count()
                if user_obj.is_superuser and admin_count <= 1:
                    messages.error(request, f'无法移除 "{user_obj.username}" 的管理员权限：系统至少需要一个管理员')
                else:
                    user_obj.is_staff = False
                    user_obj.is_superuser = False
                    user_obj.save()
                    messages.success(request, f'已移除 {user_obj.username} 的管理员权限')
            else:
                user_obj.is_staff = True
                user_obj.is_superuser = True
                user_obj.save()
                messages.success(request, f'已将 {user_obj.username} 设为管理员')

        elif action == 'toggle_staff':
            user_obj.is_staff = not user_obj.is_staff
            user_obj.save(update_fields=['is_staff'])
            status = '启用' if user_obj.is_staff else '停用'
            messages.success(request, f'{user_obj.username} 的 staff 状态已{status}')

        return redirect('admin_user_list')

    return render(request, 'accounts/user_edit.html', {
        'user_obj': user_obj,
        'groups': groups,
    })


@staff_member_required
def admin_group_list(request):
    groups = UserGroup.objects.annotate(user_count=Count('users')).order_by('-is_default', 'name')
    return render(request, 'accounts/group_list.html', {'groups': groups})


@staff_member_required
def admin_group_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        quota = request.POST.get('quota', '')
        is_default = request.POST.get('is_default') == 'on'

        if not name:
            messages.error(request, '组名称不能为空')
            return render(request, 'accounts/group_form.html', {'group': None})

        try:
            quota_bytes = int(quota)
            if quota_bytes < 1:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, '请输入有效的配额数值')
            return render(request, 'accounts/group_form.html', {'group': None})

        if UserGroup.objects.filter(name=name).exists():
            messages.error(request, f'组 "{name}" 已存在')
            return render(request, 'accounts/group_form.html', {'group': None})

        UserGroup.objects.create(name=name, storage_quota=quota_bytes, is_default=is_default)
        messages.success(request, f'用户组 "{name}" 创建成功')
        return redirect('admin_group_list')

    return render(request, 'accounts/group_form.html', {'group': None})


@staff_member_required
def admin_group_edit(request, pk):
    group = get_object_or_404(UserGroup, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        quota = request.POST.get('quota', '')
        is_default = request.POST.get('is_default') == 'on'

        if not name:
            messages.error(request, '组名称不能为空')
            return render(request, 'accounts/group_form.html', {'group': group})

        try:
            quota_bytes = int(quota)
            if quota_bytes < 1:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, '请输入有效的配额数值')
            return render(request, 'accounts/group_form.html', {'group': group})

        if UserGroup.objects.filter(name=name).exclude(pk=group.pk).exists():
            messages.error(request, f'组 "{name}" 已存在')
            return render(request, 'accounts/group_form.html', {'group': group})

        old_quota = group.storage_quota
        group.name = name
        group.storage_quota = quota_bytes
        group.is_default = is_default
        group.save()

        # 如果配额变更，更新组内所有用户的配额
        if quota_bytes != old_quota:
            User.objects.filter(group=group).update(storage_quota=quota_bytes)
            messages.success(request, f'用户组 "{name}" 更新成功，{User.objects.filter(group=group).count()} 个用户配额已同步')
        else:
            messages.success(request, f'用户组 "{name}" 更新成功')

        return redirect('admin_group_list')

    return render(request, 'accounts/group_form.html', {'group': group})


@staff_member_required
def admin_group_delete(request, pk):
    group = get_object_or_404(UserGroup, pk=pk)
    user_count = group.users.count()

    if request.method == 'POST':
        if group.is_default:
            messages.error(request, '无法删除默认用户组，请先设置其他组为默认')
            return redirect('admin_group_list')

        # 移除组关联
        group.users.update(group=None)
        name = group.name
        group.delete()
        messages.success(request, f'用户组 "{name}" 已删除（{user_count} 个用户被移出该组）')
        return redirect('admin_group_list')

    return render(request, 'accounts/group_delete_confirm.html', {
        'group': group,
        'user_count': user_count,
    })
