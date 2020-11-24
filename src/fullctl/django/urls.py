from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.conf import settings

import fullctl.django.autocomplete.views

urlpatterns = [
    path(
        "api/account/",
        include(
            ("fullctl.django.rest.urls.account", "fullctl_account_api"),
            namespace="fullctl_account_api",
        ),
    ),
    path(
        "autocomplete/pdb/ix",
        fullctl.django.autocomplete.views.peeringdb_ix.as_view(),
        name="pdb ix autocomplete",
    ),
    path(
        "autocomplete/pdb/org",
        fullctl.django.autocomplete.views.peeringdb_org.as_view(),
        name="pdb org autocomplete",
    ),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="common/auth/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="/login"), name="logout"),
    path(
        "apidocs/swagger",
        TemplateView.as_view(
            template_name="common/apidocs/swagger.html",
        ),
        name="swagger",
    ),
    path(
        "apidocs/redoc",
        TemplateView.as_view(
            template_name="common/apidocs/redoc.html",
        ),
        name="redoc",
    ),
]
