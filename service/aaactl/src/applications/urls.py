from django.urls import path

import applications.views

urlpatterns = [
    path("status/", applications.views.status, name="status"),
]
