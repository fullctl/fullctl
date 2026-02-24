from django_prefixctl.models import Instance

from fullctl.django.rest.decorators import grainy_endpoint as _grainy_endpoint
from fullctl.django.rest.decorators import grainy_file_response as _grainy_file_response


class grainy_endpoint(_grainy_endpoint):
    def __init__(self, *args, **kwargs):
        super().__init__(
            instance_class=Instance,
            explicit=kwargs.pop("explicit", False),
            *args,
            **kwargs,
        )
        if "namespace" not in kwargs:
            self.namespace += ["prefixctl"]


class grainy_file_response(_grainy_file_response):
    def __init__(self, *args, **kwargs):
        super().__init__(
            instance_class=Instance,
            explicit=kwargs.pop("explicit", False),
            *args,
            **kwargs,
        )
        if "namespace" not in kwargs:
            self.namespace += ["prefixctl"]
