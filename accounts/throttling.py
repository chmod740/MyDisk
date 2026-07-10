import hashlib

from django.core.cache import cache


def _cache_key(namespace, identifier):
    digest = hashlib.sha256(str(identifier).encode('utf-8')).hexdigest()
    return f'throttle:{namespace}:{digest}'


def throttle_exceeded(namespace, identifier, limit=5):
    return int(cache.get(_cache_key(namespace, identifier), 0) or 0) >= limit


def record_failure(namespace, identifier, timeout=300):
    key = _cache_key(namespace, identifier)
    if cache.add(key, 1, timeout=timeout):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=timeout)
        return 1


def clear_failures(namespace, identifier):
    cache.delete(_cache_key(namespace, identifier))


def request_identifier(request, subject=''):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    address = forwarded.split(',', 1)[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '')
    return f'{address}:{subject}'.lower()
