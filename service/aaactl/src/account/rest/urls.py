import account.rest.route
import account.rest.views
from django.urls import include, path

urlpatterns = [path("", include(account.rest.route.router.urls))]
