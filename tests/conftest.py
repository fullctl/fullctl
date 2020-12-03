import pytest
from tests.django_tests.fixtures import *


#FIXME: move this out
import tests.django_tests.project.settings
from django.conf import settings
settings.configure(**tests.django_tests.project.settings.__dict__)

