from django_handleref.admin import VersionAdmin
from reversion.admin import VersionAdmin as ReversionAdmin


# Register your models here.
class BaseAdmin(VersionAdmin, ReversionAdmin):
    readonly_fields = ("version",)
