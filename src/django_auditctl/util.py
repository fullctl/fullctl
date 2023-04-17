__all__ = [
    "parts_to_object_id",
]


# TODO: move to fullctl/fullctl
def parts_to_object_id(version, org_tag, ref_tag, ref_id, delimiter="-"):
    """Convert parts to object id"""

    # if ref_tag has dots in it, replace with delimiter
    ref_tag = ref_tag.replace("/", delimiter).replace(".", delimiter)

    return f"{version}{delimiter}{org_tag}{delimiter}{ref_tag}{delimiter}{ref_id}"

    # return f"{version}.{org_tag}.{ref_tag}.{ref_id}"
