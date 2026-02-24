import structlog
from django.conf import settings
from peeringdb import resource
from peeringdb.client import Client

from fullctl.django.management.commands.base import CommandInterface

log = structlog.get_logger("django")


class Command(CommandInterface):
    """
    Pull peeringdb updates
    """

    always_commit = True

    def add_arguments(self, parser):
        parser.add_argument("--pdb-url", default=settings.PDB_API_URL)

    def run(self, *args, **kwargs):

        self.pdburl = kwargs.get("pdb_url")
        self.username = getattr(settings, "PDB_API_USERNAME", "")
        self.password = getattr(settings, "PDB_API_PASSWORD", "")
        self.api_key = getattr(settings, "PDB_API_KEY", "")

        log.info(
            "Running peeringdb sync",
            pdb_url=self.pdburl,
            api_key_set=bool(self.api_key),
            username_set=bool(self.username),
        )

        self.sync()

    def sync(self):
        self.log_info(f"Syncing from {self.pdburl}")
        settings.USE_TZ = False

        config = {
            "sync": {
                "url": self.pdburl,
                "timeout": 0,
            },
            "orm": {
                "backend": "django_peeringdb",
                "migrate": True,
                "database": settings.DATABASES["default"],
            },
            "log": {
                "allow_other_loggers": True,
            },
        }

        if self.api_key:
            config["sync"]["api_key"] = self.api_key
            self.log_info(f"Using API key for sync: prefix {self.api_key[:8]}")
        elif self.username and self.password:
            config["sync"]["user"] = self.username
            config["sync"]["password"] = self.password
            self.log_info(f"Using username/password for sync: {self.username}")
        else:
            self.log_info(
                "No authentication configured for sync, using anonymous access - this may cause rate limiting issues. Set PDB_API_KEY or PDB_API_USERNAME and PDB_API_PASSWORD to configure authentication."
            )

        client = Client(config)
        client.updater.update_all(resource.all_resources(), since=None)
