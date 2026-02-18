from django_grainy.decorators import grainy_view


class org_view:
    def __init__(self, namespace, explicit=False):
        self.namespace = namespace
        self.explicit = explicit

    def __call__(self, fn):
        decorator = self

        def wrapped(request, *args, **kwargs):
            fn_inner = grainy_view(
                [request.selected_org] + decorator.namespace,
                explicit=decorator.explicit,
            )(fn)

            return fn_inner(request, *args, **kwargs)

        wrapped.__name__ = fn.__name__

        return wrapped
