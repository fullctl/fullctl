from django.db import models
from django.utils.translation import gettext as _
from django_handleref.models import HandleRefModel as SoftDeleteHandleRefModel

# Create your models here.


class HandleRefModel(SoftDeleteHandleRefModel):
    """
    Like handle ref, but with hard delete
    """

    status = models.CharField(
        max_length=12,
        default="ok",
        choices=(
            ("ok", _("Ok")),
            ("pending", _("Pending")),
            ("deactivated", _("Deactivated")),
            ("failed", _("Failed")),
            ("expired", _("Expired")),
        ),
    )

    class Meta:
        abstract = True

    def delete(self):
        return super().delete(hard=True)
