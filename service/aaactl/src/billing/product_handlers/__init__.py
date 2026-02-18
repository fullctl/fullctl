import importlib

from django.conf import settings

HANDLERS = []

for handler_path in settings.BILLING_HANDLERS:
    path = handler_path.split(".")
    class_name = path[-1]
    module_path = ".".join(path[:-1])

    _mod = importlib.import_module(module_path)
    _class = getattr(_mod, class_name)
    HANDLERS.append(_class)


def choices():
    r = [("", "Not set")]
    for handler in HANDLERS:
        r.append((handler.id, handler.name))
    return r
