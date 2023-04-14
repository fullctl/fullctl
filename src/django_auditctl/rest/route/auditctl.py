from rest_framework import routers

router = routers.DefaultRouter()


def route(viewset):
   
    # route api / id version

    version = r"v(?P<version>[^/]+)"

    # route org slug

    org_slug = r"(?P<org_tag>[^/]+)"

    # route object tag

    object_tag = r"(?P<ref_tag>.+)"

    # route object id

    object_id = r"(?P<ref_id>[^/]+)"

    # join all into a regex string

    prefix = f"{version}/{org_slug}/{object_tag}/{object_id}"

    router.register(prefix, viewset, basename="audit")
    return viewset
