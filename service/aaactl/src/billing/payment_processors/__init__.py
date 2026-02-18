import importlib

from django.conf import settings

PROCESSORS = {}

for processor_path in settings.BILLING_PROCESSORS:
    path = processor_path.split(".")
    class_name = path[-1]
    module_path = ".".join(path[:-1])

    _mod = importlib.import_module(module_path)
    _class = getattr(_mod, class_name)
    PROCESSORS[_class.id] = _class


def choices():
    r = []
    for processor in PROCESSORS.values():
        r.append((processor.id, processor.name))
    return r


def default():
    for processor in PROCESSORS.values():
        return processor
