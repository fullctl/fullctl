from django.conf import settings

# FIXME: move this out
import tests.django_tests.project.settings
from tests.django_tests.fixtures import *  # noqa: F401, F403

settings.configure(**tests.django_tests.project.settings.__dict__)
