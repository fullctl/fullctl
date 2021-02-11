from django.urls import include, path

import fullctl.django.rest.route.account
import fullctl.django.rest.views.account

urlpatterns = [
    path("", include(fullctl.django.rest.route.account.router.urls)),
]
