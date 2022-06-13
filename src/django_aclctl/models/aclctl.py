import json
import secrets

import fullctl.django.tasks
import reversion
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_grainy.decorators import grainy_model
from fullctl.django.models.abstract.base import HandleRefModel
from fullctl.django.models.concrete import Instance

__all__ = (
    "Instance",
)
