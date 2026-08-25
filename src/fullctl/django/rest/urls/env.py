from django.urls import include, path

import fullctl.django.rest.route.env
import fullctl.django.rest.views.env  # noqa: F401 — @route registration side effect

urlpatterns = [
    path("", include(fullctl.django.rest.route.env.router.urls)),
]
