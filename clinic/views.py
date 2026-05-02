from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404


def favicon(request):
    favicon_path = Path(settings.BASE_DIR) / 'static' / 'favicon.svg'
    if not favicon_path.exists():
        raise Http404('Favicon not found')
    return FileResponse(favicon_path.open('rb'), content_type='image/svg+xml')
