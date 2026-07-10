import os

os.environ.setdefault('DJANGO_DEBUG', 'true')
os.environ.setdefault('DJANGO_SECRET_KEY', 'django-insecure-development-only-key')
os.environ.setdefault('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver')

from .settings import *  # noqa: E402,F403
