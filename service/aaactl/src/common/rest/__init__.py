import datetime
import json

import django_countries
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, connection
from django.http import Http404
from rest_framework import renderers, status
from rest_framework.response import Response
from rest_framework.utils import encoders
from rest_framework.views import exception_handler as drf_exception_handler

HANDLEREF_FIELDS = ["id", "status", "created", "updated"]


def exception_handler(exc, context):
    """
    Custom exception handler for REST responses

    Currently used to properly turn django ObjectDoesNotExist
    errors into 404 api responses.
    """

    # call default handler first

    response = Response({})
    if isinstance(exc, ObjectDoesNotExist):
        response.data = {"errors": {"non_field_errors": f"{exc}"}}
        response.status_code = 404
    elif isinstance(exc, IntegrityError):
        response.data = {"non_field_errors": f"{exc}"}
        response.status_code = 400
    elif isinstance(exc, Http404):
        if getattr(context.get("request"), "destroyed", False):
            return Response({}, status=status.HTTP_204_NO_CONTENT)
        else:
            response.status_code = 404
    else:
        response = drf_exception_handler(exc, context)

    return response


class JSONEncoder(encoders.JSONEncoder):
    """
    Custom json encoder that can handle

    - datetime serialization
    - django country field serialization
    """

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()

        if isinstance(obj, django_countries.fields.Country):
            return str(obj)

        return encoders.JSONEncoder.default(self, obj)


class JSONRenderer(renderers.JSONRenderer):
    """
    Extended JSON Renderer that

    - wraps data in a container
    - makes sure data is always returned as a list
    """

    charset = "utf-8"

    def render(self, data, media_type=None, renderer_context=None):
        status = renderer_context.get("response").status_code

        container = {"data": [], "errors": {}}

        # FIXME: should be a config value to disable/enable profile
        # info in the response data
        container["profiling"] = {"queries": len(connection.queries)}

        if status >= 400:
            container["errors"] = data
        else:
            if isinstance(data, dict):
                container["data"].append(data)
            elif isinstance(data, list):
                container["data"].extend(data)
            else:
                raise TypeError(
                    "REST Renderer does not know what to do with data type `{}` at root".format(
                        type(data)
                    )
                )
        data = container
        indent = None
        request = renderer_context.get("request")
        if request:
            if "pretty" in request.GET:
                indent = 2
        return json.dumps(data, cls=JSONEncoder, indent=indent)
