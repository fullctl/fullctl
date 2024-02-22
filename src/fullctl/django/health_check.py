"""
Defines an extendible healthcheck process for FullCtl services.
"""
from django.db import connection

__all__ = [
    "register",
    "check_all",
    "HEALTH_CHECKS",
]

# holds all registered health checks
HEALTH_CHECKS = {}


class register:
    """
    Registers a health check function.

    The function must return a boolean value, True if the service is healthy,
    False otherwise.

    The function will be called with no arguments.
    """

    def __init__(self, name):
        self.name = name

    def __call__(self, func):
        HEALTH_CHECKS[self.name] = func
        return func


def check_all() -> dict:
    """
    Run all registered health checks.
    """
    results = {}
    for name, func in HEALTH_CHECKS.items():
        results[name] = func()

    return results


@register("db")
def health_check_db():
    """
    Performs a simple database version query
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT version()")
