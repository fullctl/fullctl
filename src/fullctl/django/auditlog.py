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
    "info": contextvars.ContextVar("auditlog_info"),
    "data": contextvars.ContextVar("auditlog_data"),
}


def model_tag(model):

    """
    Return the model identifier tag used for auditlog actions

    Will prefer a handlerf tag if it exists, otherwise a lowercase
    version of the model name will be returned.
    """

    try:
        return model.HandleRef.tag
    except AttributeError:
        return model.__name__.lower()


def get_config(model):

    """
    Returns the AuditLog meta class for the model if it
    exists.

    Will raise AttributeError if it does not exist
    """

    return model.AuditLog


def is_enabled(model):

    """
    Returns whether the specified model is enabled for audit
    log.

    By default all reversioned models are enabled.

    To disable a model set `enabled=False` on the AuditLog
    meta class for the model
    """

    try:
        al_config = get_config(model)
    except AttributeError:
        return True

    return getattr(al_config, "enabled", True)


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
        self._init_variable("info", default="")
        self._init_variable("data", default={})
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

    def log(self, action, log_object=None, info=None, **data):

        if data:
            self.set("data", data)

        if info is not None:
            self.set("info", info)

        if not self.get("org") and log_object:
            if hasattr(log_object, "org"):
                self.set("org", log_object.org)
            elif isinstance(log_object, Organization):
                self.set("org", log_object)

        entry = AuditLog(
            user=self.get("user"),
            key=self.get("key"),
            org=self.get("org"),
            data=json.dumps(self.get("data")),
            action=action,
            info=self.get("info"),
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
