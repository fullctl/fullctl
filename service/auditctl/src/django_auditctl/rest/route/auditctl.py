from rest_framework import routers

router = routers.DefaultRouter()


def route(viewset):
    # route api / id version (make it optional with a '?')
    version = r"(?P<version>[^/]+)?"

    # route org slug (make it optional with a '?')
    org_slug = r"(?P<org_tag>[^/]+)?"

    # route object tag (make it optional with a '?')
    object_tag = r"(?P<ref_tag>.+)?"

    # route object id (make it optional with a '?')
    object_id = r"(?P<ref_id>[^/]+)?"

    # join all into a regex string, making delimiters optional
    prefix = f"{version}/?{org_slug}/?{object_tag}/?{object_id}"

    # Make trailing slash optional in the regex string
    prefix_with_optional_trailing_slash = f"{prefix}/?"

    router.register(prefix_with_optional_trailing_slash, viewset, basename="audit")
    return viewset
