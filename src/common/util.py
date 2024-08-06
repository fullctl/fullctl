from django.conf import settings

__all__ = [
    "format_logo_url",
]

LOGO_URL_VARIABLES = {
    "version": settings.PACKAGE_VERSION,
    "static_path": settings.STATIC_URL.strip("/"),
}


def format_logo_url(url: str) -> str:
    if not url:
        return url
    try:
        return url.format(**LOGO_URL_VARIABLES)
    except KeyError:
        return url
