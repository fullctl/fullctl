import django_auditctl.rest.route.auditctl
import django_auditctl.rest.views.auditctl
from django.urls import include, path

urlpatterns = [
    path("", include(django_auditctl.rest.route.auditctl.router.urls)),
]
