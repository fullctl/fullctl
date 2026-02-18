from fullctl.django.rest.decorators import grainy_endpoint as _grainy_endpoint

import django_devicectl.models as models


class grainy_endpoint(_grainy_endpoint):
    def __init__(self, *args, **kwargs):
        super().__init__(
            instance_class=models.Instance,
            explicit=kwargs.pop("explicit", False),
            *args,
            **kwargs
        )
        if "namespace" not in kwargs:
            self.namespace += ["devicectl"]
