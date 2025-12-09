from django.urls import include, path

import applications.rest.route
import applications.rest.views

urlpatterns = [path("", include(applications.rest.route.router.urls))]
