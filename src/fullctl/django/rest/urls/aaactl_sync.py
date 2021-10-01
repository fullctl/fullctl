from django.urls import include, path

import fullctl.django.rest.route.aaactl_sync
import fullctl.django.rest.views.aaactl_sync

urlpatterns = [
    path("", include(fullctl.django.rest.route.aaactl_sync.router.urls)),
]
