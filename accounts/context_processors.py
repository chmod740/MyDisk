from .models import SiteSettings


def site_name(request):
    try:
        settings = SiteSettings.get_settings()
        return {'site_name': settings.site_name}
    except Exception:
        return {'site_name': 'DjangoDisk'}
