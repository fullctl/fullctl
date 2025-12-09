from django.urls import include, path

import django_auditctl.rest.route.auditctl
import django_auditctl.rest.views.auditctl

urlpatterns = [
    path("", include(django_auditctl.rest.route.auditctl.router.urls)),
]
