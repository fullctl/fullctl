from django.urls import include, path
from django.conf import settings

# import django_aclctl.rest.views

from django_aclctl import views
from django_aclctl.models.aclctl import FilterRuleTemplate

import fullctl.django.rest.urls.service_bridge_proxy as proxy
from fullctl.django.views.template import TemplateFileView

proxy.setup("prefixctl", proxy.proxy_api(
    "prefixctl",
    settings.PREFIXCTL_HOST,
    [
        ("pfxset/{org_tag}", "pfxset/<str:org_tag>/", "list"),
    ],
))

urlpatterns = proxy.urlpatterns(["prefixctl"])

urlpatterns += [
    path(
        "api/",
        include(
            ("django_aclctl.rest.urls.aclctl", "aclctl_api"),
            namespace="aclctl_api",
        ),
    ),
    path("tmpl/filter_rule_template/<str:template_type>/", TemplateFileView.as_view(TemplateModel=FilterRuleTemplate), name='default-template'),
    path("<str:org_tag>/", views.view_instance, name="aclctl-home"),
    path("", views.org_redirect),
]
