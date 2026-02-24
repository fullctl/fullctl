import applications.rest.route
import applications.rest.views
from django.urls import include, path

urlpatterns = [path("", include(applications.rest.route.router.urls))]
