import applications.views
from django.urls import path

urlpatterns = [
    path("status/", applications.views.status, name="status"),
]
