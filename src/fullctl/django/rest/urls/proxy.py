from importlib import import_module
import requests

from django.http import JsonResponse
from django.urls import path, include

PROXIED = {}

def proxy_api(service, host, endpoints):

    """
    proxies a fullctl service's api with it's endpoints
    exposed to the local service's api 1:1
    """

    paths = [
        proxy_api_endpoint(service, host, endpoint)
        for endpoint in endpoints
    ]

    return include(paths)


def proxy_api_endpoint(service, host, tag):

    def view_proxy(request, org_tag, *args, **kwargs):
        api_key = request.user.key_set.first()
        method = request.method.lower()
        request_fn = getattr(requests, method)

        _kwargs = {}

        if method in ["post","put","patch"]:
            _kwargs.update(data=request.data)

        response = request_fn(f"{host}/api/{org_tag}/{tag}", params = {"key":api_key.key})
        print("proxied response in", response.elapsed.total_seconds())
        return JsonResponse(response.json(), status=response.status_code)

    return path(f"{tag}/", view_proxy, name=f"proxies-api-{service}-{tag}")


def setup(service, patterns):

    if service in PROXIED:
        raise ValueError(f"Proxied api for service {service} already setup")

    PROXIED[service] = patterns

def urlpatterns(supported_services):
    urlpatterns = []

    for service in supported_services:
        import_module(f"django_{service}.rest.urls.proxy")

    for service, patterns in PROXIED.items():
        urlpatterns.append(
            path(
                "api/<str:org_tag>/",
                patterns
            )
        )

    return urlpatterns


