from django.conf import settings

# FIXME: move this out
import tests.django_tests.project.settings
from tests.django_tests.fixtures import *  # noqa: F401, F403


_settings = dict(
    [
        (k, v)
        for k, v in tests.django_tests.project.settings.__dict__.items()
        if not k.startswith("_")
    ]
)

settings.configure(**_settings)
