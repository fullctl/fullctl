"""
Auditlogging functionality
"""

import json
import inspect
import contextvars

from fullctl.django.models import AuditLog

CTX_VARS = {
    "info": contextvars.ContextVar("auditlog_info"),
    "user": contextvars.ContextVar("auditlog_user"),
    "user_key": contextvars.ContextVar("auditlog_user_key"),
    "org_key": contextvars.ContextVar("auditlog_org_key"),
    "revision": contextvars.ContextVar("auditlog_revision"),
    "action": contextvars.ContextVar("auditlog_action"),
    "data": contextvars.ContextVar("auditlog_data"),
}


class Context:
    def __init__(self):
        self.fields = {}
        self.entires = []

    def __enter__(self):
        self._init_variable("info", default="")

    def __exit__(self):
        for entry in self.entries:
            entry.save()

        for name, field in self.fields.items():
            if field["token"]:
                field["ctxvar"].reset(field["token"])


    def _init_variable(self, name, default=None)
        ctxvar = CTX_VARS.get(name)
        self.fields[name] = {"ctxvar":ctxvar, "value":default, "token":None}
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


    def log(self, action, info=None, log_object=None, **data):
        entry = AuditLog(
            user = self.get("user"),
            user_key = self.get("user_key"),
            org_key = self.get("org_key"),
            data = json.dumps(data),
            action = action,
            info = info,
            log_object = log_object
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

            param = inspect.getcallargs(fn, *args, **kwargs)

            request = param.get("request")
            user = param.get("user")

            with Context() as ctx:

                if user:
                    ctx.set("user", user)
                elif request:
                    ctx.set("user", request.user)

                return fn(*args, auditlog=ctx, **kwargs)
