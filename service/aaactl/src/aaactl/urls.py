"""aaactl URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

import account.views.auth
import oauth2_provider.views as oauth2_views
from aaactl.error_handlers import (
    handle_error_400,
    handle_error_401,
    handle_error_403,
    handle_error_404,
    handle_error_500,
)
from account.grainy_ext import APIKeyAuthenticator
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django_grainy.remote import ProvideGet, ProvideLoad

# OAuth2 provider endpoints
oauth2_endpoint_views = [
    path("authorize/", oauth2_views.AuthorizationView.as_view(), name="authorize"),
    path("token/", oauth2_views.TokenView.as_view(), name="token"),
    path("revoke-token/", oauth2_views.RevokeTokenView.as_view(), name="revoke-token"),
]


# we only want to expose the oauth application management views
# while in a testing environment

if settings.DEBUG:
    # OAuth2 Application Management endpoints
    oauth2_endpoint_views += [
        path("applications/", oauth2_views.ApplicationList.as_view(), name="list"),
        path(
            "applications/register/",
            oauth2_views.ApplicationRegistration.as_view(),
            name="register",
        ),
        path(
            "applications/<pk>/",
            oauth2_views.ApplicationDetail.as_view(),
            name="detail",
        ),
        path(
            "applications/<pk>/delete/",
            oauth2_views.ApplicationDelete.as_view(),
            name="delete",
        ),
        path(
            "applications/<pk>/update/",
            oauth2_views.ApplicationUpdate.as_view(),
            name="update",
        ),
    ]

    # OAuth2 Token Management endpoints
    oauth2_endpoint_views += [
        path(
            "authorized-tokens/",
            oauth2_views.AuthorizedTokensListView.as_view(),
            name="authorized-token-list",
        ),
        path(
            "authorized-tokens/<pk>/delete/",
            oauth2_views.AuthorizedTokenDeleteView.as_view(),
            name="authorized-token-delete",
        ),
    ]

urlpatterns = []

if settings.EXPOSE_ADMIN:
    urlpatterns += [
        path("admin/", admin.site.urls),
    ]

urlpatterns += [
    # account
    path(
        "account/auth/o/",
        include(
            (oauth2_endpoint_views, "oauth2_provider"), namespace="oauth2_provider"
        ),
    ),
    path("account/", include(("account.urls", "account"), namespace="account")),
    path(
        "api/account/",
        include(("account.rest.urls", "account_api"), namespace="account_api"),
    ),
    # billing
    path("billing/", include(("billing.urls", "billing"), namespace="billing")),
    path(
        "api/billing/",
        include(("billing.rest.urls", "billing_api"), namespace="billing_api"),
    ),
    # service applications
    path(
        "apps/",
        include(("applications.urls", "applications"), namespace="applications"),
    ),
    path(
        "api/apps/",
        include(
            ("applications.rest.urls", "applications_api"), namespace="applications_api"
        ),
    ),
    # social-auth urls
    path("social/", include("social_django.urls", namespace="social")),
    # support login shortcut
    path("login-support/", account.views.auth.login_support, name="login-support"),
    # grainy
    path(
        "grainy/get/<str:namespace>/",
        ProvideGet.as_view(authenticator_cls=APIKeyAuthenticator),
        name="grainy-get",
    ),
    path(
        "grainy/load/",
        ProvideLoad.as_view(authenticator_cls=APIKeyAuthenticator),
        name="grainy-load",
    ),
    path(
        "", RedirectView.as_view(pattern_name="account:controlpanel", permanent=False)
    ),
    path("", include("fullctl.django.urls")),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler500 = handle_error_500
handler404 = handle_error_404
handler403 = handle_error_403
handler401 = handle_error_401
handler400 = handle_error_400
