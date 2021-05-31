"""
Auditlogging functionality
"""

import json
import inspect
import contextvars

from django.http import HttpRequest
from django.contrib.auth import get_user_model
from rest_framework.request import Request

from fullctl.django.models import AuditLog, Organization

User = get_user_model()

CTX_VARS = {
    "user": contextvars.ContextVar("auditlog_user"),
    "org": contextvars.ContextVar("auditlog_org"),
    "key": contextvars.ContextVar("auditlog_key"),
}


class Context:

    """
    Auditlog context manager
    """

    def __init__(self):

        # context variable fields
        self.fields = {}

        # auditlog entries to be persisted in the active
        # context
        self.entries = []

    def __enter__(self):
        self._init_variable("user")
        self._init_variable("key")
        self._init_variable("org")
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if not exc_type:
            for entry in self.entries:
                entry.save()

        for name, field in self.fields.items():
            if field["token"]:
                field["ctxvar"].reset(field["token"])

    def _init_variable(self, name, default=None):
        ctxvar = CTX_VARS.get(name)
        self.fields[name] = {"ctxvar": ctxvar, "value": default, "token": None}
        try:
            self.fields[name].update(value=ctxvar.get())
        except LookupError:
            pass

    def set(self, name, value):
        fld = self.fields[name]
        fld["token"] = fld["ctxvar"].set(value)
        fld["value"] = value

    def get(self, name):
        return self.fields[name].get("value")

    def log(self, action, info="", log_object=None, **data):
        entry = AuditLog(
            user=self.get("user"),
            key=self.get("key"),
            org=self.get("org"),
            data=json.dumps(data),
            action=action,
            info=info,
            log_object=log_object,
        )
        self.entries.append(entry)


class auditlog:

    """
    decorator for auditlog context
    """

    def __init__(self):
        pass

    def __call__(self, fn):
        def wrapped(*args, **kwargs):

            params = inspect.getcallargs(fn, *args, **kwargs)
            request = None
            user = None
            org = None
            api_key = None

            for arg in list(params["args"]) + list(params["kwargs"].values()):
                if isinstance(arg, (HttpRequest, Request)):
                    request = arg
                elif isinstance(arg, User):
                    user = arg
                elif isinstance(arg, Organization):
                    arg = org

                if user and request and org:
                    break

            if request and not user:
                user = request.user

            if request and hasattr(request, "api_key"):
                api_key = request.api_key[:8]

            if request and not org and hasattr(request, "org"):
                org = request.org

            with Context() as ctx:
                if user:
                    ctx.set("user", user)
                if api_key:
                    ctx.set("key", api_key)
                if org:
                    ctx.set("org", org)
                return fn(*args, auditlog=ctx, **kwargs)

        wrapped.__name__ = fn.__name__
        return wrapped
