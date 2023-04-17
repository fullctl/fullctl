import pydantic
from django.utils.translation import ugettext_lazy as _
from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import ModelSerializer
from rest_framework import serializers

import django_auditctl.enum as enum
import django_auditctl.models as models
import django_auditctl.schema as schema

Serializers, register = serializer_registry()


# TODO move to fullctl/fullctl
class PydanticSerializer(serializers.Serializer):

    """
    Serializer that allows for validation of JSONFields
    agaisnt a pydantic model
    """

    class Meta:
        pass

    def to_internal_value(self, data):
        try:
            print(data, type(data))
            if isinstance(data, dict):
                return self.Meta.model(**data).dict()
            elif isinstance(data, list):
                result = [self.Meta.model(**item).dict() for item in data]
                # strip all the None and empty dicts before returning the list
                return [item for item in result if item]
        except pydantic.ValidationError as e:
            drf_errors = {err["loc"][0]: [err["msg"]] for err in e.errors()}
            raise serializers.ValidationError(drf_errors)

    def to_representation(self, instance):
        return instance


# TODO move to fullctl/fullctl
class DynamicPydanticSerializer(PydanticSerializer):

    """
    Serializer that allows for validation of JSONFields
    agaisnt a pydantic model, where the model is determined
    through a schema_id property onf the request.
    """

    class Meta:
        pass

    def __init__(self, schema_id="default", *args, **kwargs):
        # Get the Pydantic model from the registry
        print("GETTING SCHEMA", schema_id, schema.get_model_from_registry(schema_id))
        self.Meta.model = schema.get_model_from_registry(schema_id)

        if not self.Meta.model:
            self.Meta.model = schema.get_model_from_registry("default")

        # Call the parent constructor
        super().__init__(*args, **kwargs)


# TODO move to fullctl/fullctl
class DynamicPydanticField(serializers.Field):

    """
    Serializer field that allows for validation of JSONFields
    agaisnt a pydantic model, where the model is determined
    through a schema_id property onf the request.
    """

    def __init__(self, schema_id="default", *args, **kwargs):
        self.schema_id = schema_id
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        serializer = DynamicPydanticSerializer(schema_id=self.schema_id)
        return serializer.to_internal_value(data)

    def to_representation(self, value):
        serializer = DynamicPydanticSerializer(schema_id=self.schema_id)
        return serializer.to_representation(value)


class ErrorDetails(PydanticSerializer):

    """
    Validate `error` content using pydantic
    """

    class Meta:
        model = schema.ErrorDetails


@register
class Event(ModelSerializer):
    """
    Serializes event objects
    """

    # error takes JSON data, so we need to validate it
    # using pydantic
    error = ErrorDetails(required=False, allow_null=True)

    # data takes JSON data, and is validated using
    # pydantic with a DynamicPydanticSerializer because the
    # data structure will change depending on object_id
    data = DynamicPydanticField(required=False, allow_null=True)

    # by default fullctl ModelSerializer defines `status` as a read only
    # field, so redefine it here.
    status = serializers.ChoiceField(choices=enum.STATUS, required=False, default="ok")

    class Meta:
        model = models.Event
        fields = [
            "id",
            "object_id",
            "data",
            "error",
            "org",
            "user",
            "status",
        ]

    def __init__(self, *args, **kwargs):
        # Retrieve the schema_id, e.g., from the request or any other source
        schema_id = kwargs.get("context", {}).get("object_id", "default")
        self.fields["data"].schema_id = schema_id

        super().__init__(*args, **kwargs)
