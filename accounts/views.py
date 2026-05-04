from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from .models import User, SiteSettings
from .captcha import generate_captcha, verify_captcha


def captcha_image(request):
    """返回验证码图片"""
    img_bytes = generate_captcha(request)
    return HttpResponse(img_bytes, content_type='image/png')


def register_view(request):
    settings = SiteSettings.get_settings()

    if not settings.allow_registration:
        messages.error(request, '当前站点已关闭注册功能')
        return render(request, 'accounts/register.html')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        errors = []

        # 验证码检查
        if settings.require_captcha_register:
            captcha_answer = request.POST.get('captcha', '').strip()
            if not verify_captcha(request, captcha_answer):
                errors.append('验证码错误')

        if not username or not password:
            errors.append('用户名和密码不能为空')
        if password != password2:
            errors.append('两次密码输入不一致')
        if len(password) < 6:
            errors.append('密码长度至少6位')
        if User.objects.filter(username=username).exists():
            errors.append('用户名已存在')
        if email and User.objects.filter(email=email).exists():
            errors.append('邮箱已被注册')

        if errors:
            for e in errors:
                messages.error(request, e)
            # 重新生成验证码
            if settings.require_captcha_register:
                generate_captcha(request)
            return render(request, 'accounts/register.html')

        user = User.objects.create_user(username=username, email=email, password=password)

        # 分配默认用户组和配额
        if settings.default_group:
            user.group = settings.default_group
            user.storage_quota = settings.default_group.storage_quota
        else:
            user.storage_quota = settings.default_storage_quota
        user.save(update_fields=['group', 'storage_quota'])

        login(request, user)
        return redirect('file_list')

    ctx = {}
    if settings.require_captcha_register:
        generate_captcha(request); ctx['captcha_required'] = True
    return render(request, 'accounts/register.html', ctx)


def login_view(request):
    settings = SiteSettings.get_settings()

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # 验证码检查
        if settings.require_captcha_login:
            captcha_answer = request.POST.get('captcha', '').strip()
            if not verify_captcha(request, captcha_answer):
                messages.error(request, '验证码错误')
                generate_captcha(request); ctx = {'captcha_required': True}
                return render(request, 'accounts/login.html', ctx)

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.GET.get('next', '')
            if next_url:
                return redirect(next_url)
            return redirect('file_list')
        messages.error(request, '用户名或密码错误')
        if settings.require_captcha_login:
            generate_captcha(request); ctx = {'captcha_required': True}
            return render(request, 'accounts/login.html', ctx)

    ctx = {}
    if settings.require_captcha_login:
        generate_captcha(request); ctx['captcha_required'] = True
    return render(request, 'accounts/login.html', ctx)


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def profile_view(request):
    user = request.user
    files_count = user.files.filter(is_deleted=False).count()
    folders_count = user.folders.filter(is_deleted=False).count()

    def format_size(b):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if b < 1024:
                return f'{b:.1f} {unit}'
            b /= 1024
        return f'{b:.1f} TB'

    ctx = {
        'files_count': files_count,
        'folders_count': folders_count,
        'storage_used_display': format_size(user.storage_used),
        'storage_quota_display': format_size(user.storage_quota),
        'usage_percent': round(user.storage_used / user.storage_quota * 100, 1) if user.storage_quota else 0,
        'user_group': user.group,
    }
    return render(request, 'accounts/profile.html', ctx)
