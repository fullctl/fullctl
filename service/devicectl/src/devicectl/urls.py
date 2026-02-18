import fullctl.django.views as views
from django.contrib import admin
from django.urls import include, path

# import django_devicectl.urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("social_django.urls", namespace="social")),
    path("", include("fullctl.django.urls")),
    path("", include("django_devicectl.urls")),
    path("", views.org_redirect),
]
