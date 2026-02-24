import django_peerctl.rest.route.peerctl
import django_peerctl.rest.views.peerctl
from django.urls import include, path

urlpatterns = [
    path("", include(django_peerctl.rest.route.peerctl.router.urls)),
]
