"""
Common mixins for prefix meta sources to provide consistent functionality
across different RIRs (Regional Internet Registries).
"""

__all__ = [
    "ObjectSeparationMixin",
]


class ObjectSeparationMixin:
    """
    Mixin to provide object type separation for whois/registry data.
    Used by RIPE Historical Whois to group referencing objects by type (mntner, org, role, etc.)
    This mixin provides methods to group whois/registry objects by their type.
    """

    def _group_objects_by_type(self, objects_data, key_field="type"):
        """
        Group objects by their type field.

        Args:
            objects_data: Can be dict, list, or other data structure containing objects
            key_field: Field name to group by (default: "type")

        Returns:
            dict: {object_type: [objects]}
        """
        grouped = {}

        if isinstance(objects_data, dict):
            for key, obj in objects_data.items():
                if isinstance(obj, dict):
                    obj_type = obj.get(key_field, "unknown")
                elif isinstance(obj, list) and obj:
                    obj_type = obj[0].get(key_field, "unknown") if isinstance(obj[0], dict) else "unknown"
                else:
                    obj_type = "unknown"

                grouped.setdefault(obj_type, []).append({key: obj})

        elif isinstance(objects_data, list):
            for obj in objects_data:
                if isinstance(obj, dict):
                    obj_type = obj.get(key_field, "unknown")
                    grouped.setdefault(obj_type, []).append(obj)

        return grouped

    def _separate_whois_objects_by_type(self, data):
        """
        Separate whois objects by type for consistent display.

        Currently only supports RIPE Historical Whois Historical data.
        This method should be called in prepare_data() or similar methods
        to add object type separation to the normalized data.

        Args:
            data: Normalized whois data

        Returns:
            dict: Data with added objects_by_type field
        """
        if not isinstance(data, dict):
            return data

        if "ripe_historical_references" in data:
            return data

        # TODO: Handle Other RIR style data

        return data
