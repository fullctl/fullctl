from django.urls import path, include

import fullctl.django.rest.views.account
import fullctl.django.rest.route.account

urlpatterns = [
    path("", include(fullctl.django.rest.route.account.router.urls)),
]
