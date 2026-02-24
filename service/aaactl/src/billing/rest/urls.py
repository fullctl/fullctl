import billing.rest.route
import billing.rest.views
from django.urls import include, path

urlpatterns = [path("", include(billing.rest.route.router.urls))]
