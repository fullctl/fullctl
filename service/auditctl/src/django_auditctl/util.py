__all__ = [
    "parts_to_object_id",
]


# TODO: move to fullctl/fullctl
def parts_to_object_id(
    version=None, org_tag=None, ref_tag=None, ref_id=None, delimiter="/"
):
    """
    Convert parts to object id

    Arguments:

    - version (`str`, optional): version string
    - org_tag (`str`, optional): organization tag
    - ref_tag (`str`, optional): reference tag
    - ref_id (`str`, optional): reference id
    - delimiter (`str`): delimiter to use

    Examples:

    >>> parts_to_object_id("v1", "org", "ref", "id")
    'v1/org/ref/id'
    """

    # Validate that the previous parts are set when a subpart is set
    if ref_id and not ref_tag:
        raise ValueError("ref_tag must be set when ref_id is set")
    if ref_tag and not org_tag:
        raise ValueError("org_tag must be set when ref_tag is set")
    if org_tag and not version:
        raise ValueError("version must be set when org_tag is set")

    # Build object_id string conditionally
    object_id_parts = [version, org_tag, ref_tag, ref_id]
    object_id = delimiter.join(part for part in object_id_parts if part)

    return object_id


def object_id_to_parts(object_id):
    """
    Returns a dict of object_id parts
    """

    parts = object_id.split("/")

    return {
        "version": parts[0] if len(parts) > 0 else None,
        "org_tag": parts[1] if len(parts) > 1 else None,
        "ref_tag": parts[2] if len(parts) > 2 else None,
        "ref_id": "/".join(parts[3:]) if len(parts) > 3 else None,
    }
