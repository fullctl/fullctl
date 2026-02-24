import prefix_meta.views as views
from django.urls import path

urlpatterns = [
    path(
        "<str:org_tag>/export/meta/prefix/location/<str:ip>/<str:masklen>",
        views.export_locations,
        name="location-export",
    )
]
