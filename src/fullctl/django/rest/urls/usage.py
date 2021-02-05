from django.urls import path, include

import fullctl.django.rest.views.usage
import fullctl.django.rest.route.usage

urlpatterns = [
    path("", include(fullctl.django.rest.route.usage.router.urls)),
]
