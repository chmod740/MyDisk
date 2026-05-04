"""API Key 认证装饰器"""
from functools import wraps
from django.http import JsonResponse
from django.utils import timezone
from .models import ApiKey


def api_key_required(view_func):
    """通过 X-Api-Key header 认证的装饰器。将 key_obj 和 user 附加到 request"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        api_key = request.headers.get('X-Api-Key', '')
        if not api_key:
            return JsonResponse({'error': 'Missing X-Api-Key header'}, status=401)

        key_obj = ApiKey.verify_key(api_key)
        if not key_obj:
            return JsonResponse({'error': 'Invalid or inactive API key'}, status=403)

        # 更新最后访问时间
        ApiKey.objects.filter(pk=key_obj.pk).update(last_accessed_at=timezone.now())

        request.api_key = key_obj
        request.user = key_obj.user
        return view_func(request, *args, **kwargs)
    return wrapper
