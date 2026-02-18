from django.urls import include, path

import billing.rest.route
import billing.rest.views

urlpatterns = [path("", include(billing.rest.route.router.urls))]
