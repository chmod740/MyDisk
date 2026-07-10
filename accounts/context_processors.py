from .models import SiteSettings
from django.db import OperationalError, ProgrammingError


def site_name(request):
    try:
        settings = SiteSettings.get_settings()
        return {'site_name': settings.site_name}
    except (OperationalError, ProgrammingError):
        return {'site_name': 'DjangoDisk'}
