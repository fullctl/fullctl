from django.urls import include, path

import account.rest.route
import account.rest.views

urlpatterns = [path("", include(account.rest.route.router.urls))]
