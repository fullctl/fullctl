from django.conf import settings
from peeringdb import initialize_backend, resource
from peeringdb.client import Client

from fullctl.django.management.commands.base import CommandInterface


class Command(CommandInterface):

    """
    Pull peeringdb updates
    """

    always_commit = True

    def add_arguments(self, parser):
        parser.add_argument("--pdburl", default="https://www.peeringdb.com/api")

    def run(self, *args, **kwargs):
        self.pdburl = kwargs.get("pdburl")
        self.username = getattr(settings, "PDB_API_USERNAME", "")
        self.password = getattr(settings, "PDB_API_PASSWORD", "")
        self.sync()

    def sync(self):
        settings.USE_TZ = False
        config = {
            "sync": {
                "url": self.pdburl,
                "user": self.username,
                "password": self.password,
                "strip_tz": 1,
                "timeout": 0,
                "only": [],
            },
            "orm": {
                "database": settings.DATABASES["default"],
                "backend": "django_peeringdb",
                "migrate": True,
            },
        }

        initialize_backend("django_peeringdb", **config["orm"])

        client = Client(config, **config)
        print("Syncing from", config["sync"]["url"])
        client.update_all(resource.all_resources())
