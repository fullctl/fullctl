import fullctl.django.rest.urls.service_bridge_proxy as proxy
from django.conf import settings
from django.urls import include, path

import django_ixctl.views as views

proxy.setup(
    "devicectl",
    proxy.proxy_api(
        "devicectl",
        settings.DEVICECTL_URL,
        [
            # facilities
            ("facility/{org_tag}", "facility/<str:org_tag>/", "facility-list"),
            # devices for each facility
            (
                "facility/{org_tag}/{fac_tag}/devices/",
                "facility/<str:org_tag>/<str:fac_tag>/devices/",
                "facility-devices",
            ),
            # virtual ports for each device
            (
                "device/{org_tag}/{pk}/virtual_ports",
                "device/<str:org_tag>/<int:pk>/virtual_ports/",
                "device-virtual-ports",
            ),
            # traffic graphs
            # LEGACY RRD / MRTG
            (
                "virtual_port/{org_tag}/{pk}/traffic",
                "virtual_port/<str:org_tag>/<int:pk>/traffic/",
                "virtual-port-traffic",
            ),
            (
                "traffic/{org_tag}/ix/{ix_id}",
                "traffic/<str:org_tag>/ix/<int:ix_id>/",
                "ix-traffic",
            ),
            # VictoriaMetrics / MRTG
            (
                "metric/mrtg/{org_tag}/graph/port/{port_id}",
                "metric/mrtg/<str:org_tag>/graph/port/<int:port_id>/",
                "port-traffic-vm-mrtg",
            ),
            (
                "metric/mrtg/{org_tag}/graph/ix/{ix_id}",
                "metric/mrtg/<str:org_tag>/graph/ix/<int:ix_id>/",
                "ix-traffic-vm-mrtg",
            ),
            # VictoriaMetrics / SFlow
            (
                "metric/sflow/{org_tag}/graph/port/{port_id}",
                "metric/sflow/<str:org_tag>/graph/port/<int:port_id>/",
                "port-traffic-vm-sflow",
            ),
            (
                "metric/sflow/{org_tag}/graph/ix/{ix_id}",
                "metric/sflow/<str:org_tag>/graph/ix/<int:ix_id>/",
                "ix-traffic-vm-sflow",
            ),
            (
                "metric/device/{org_tag}/port/{port_id}",
                "metric/device/<str:org_tag>/port/<int:port_id>/",
                "metric",
            ),
            (
                "virtual_port/{org_tag}/{pk}/metric",
                "virtual_port/<str:org_tag>/<int:pk>/metric/",
                "virtual-port-metric",
            ),
        ],
    ),
)

proxy.setup(
    "aaactl",
    proxy.proxy_api(
        "aaactl",
        settings.AAACTL_URL,
        [
            (
                "billing/org/{org_tag}/start_trial/",
                "billing/<str:org_tag>/start_trial/",
                "start-trial",
            )
        ],
    ),
)

proxy.setup(
    "prefixctl",
    proxy.proxy_api(
        "prefixctl",
        settings.PREFIXCTL_URL,
        [
            ("prefix_set/{org_tag}", "prefix_set/<str:org_tag>/", "list"),
        ],
    ),
)

urlpatterns = proxy.urlpatterns(["aaactl", "devicectl", "prefixctl"])

urlpatterns += [
    path(
        "api/",
        include(("django_ixctl.rest.urls.ixctl", "ixctl_api"), namespace="ixctl_api"),
    ),
    path(
        "<str:org_tag>/<str:ix_tag>/export/memberlist.json",
        views.export_ixf,
        name="ixf export",
    ),
    path("<str:org_tag>/<str:ix_tag>/", views.view_instance_load_ix, name="ixctl-home"),
    path(
        "<str:org_tag>/<str:ix_tag>/public/information/",
        views.public_view_redirect,
        name="ixctl-information",
    ),
    path("<str:org_tag>/", views.view_instance, name="ixctl-home"),
    path("", views.org_redirect),
]
