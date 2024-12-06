import structlog
from dateutil.parser import parse as date_parser
from django.conf import settings
from fullctl.django.models.concrete import Task
from fullctl.django.tasks import register as register_task

from prefix_meta.sources.maxmind.client import (
    MaxmindDatabaseClient,
    MaxmindFileProcessor,
)
from prefix_meta.sources.maxmind.models import MaxmindLocationData

log = structlog.get_logger("django")


@register_task
class MaxmindLoadDatabaseTask(Task):
    """
    Maxmind load database task
    Looks up the current database from Maxmind and updates the local database accordingly
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.maxmind_database_client = MaxmindDatabaseClient(
            account_id=getattr(settings, "MAXMIND_ACCOUNT_ID"),
            api_key=getattr(settings, "MAXMIND_API_KEY"),
        )

    class HandleRef:
        tag = "maxmind_load_database_task"

    def run(self, *args, **kwargs):
        """
        Run the task

        Sequence matters, city data contains more than country data
        At points where the city data and country data sharing location reference data
        we want the city data which has same and more columns as the country data
        """
        log.info("Maxmind loading country data.")
        self.handle_country_data()
        log.info("Maxmind loading city data.")
        self.handle_city_data()
        log.info("Maxmind load database task done.")

    def get_last_location_data(self, location_type: str) -> MaxmindLocationData | None:
        """
        Gets the last location data in the db
        """
        return (
            MaxmindLocationData.objects.filter(
                source_name="maxmind",
                type="location",
                location_type=location_type,
            )
            .order_by("-date")
            .first()
        )

    def load_maxmind_data(self, location_type: str):
        """
        Gets the maxmind database files and loads the files into the db
        """
        zip_file = self.maxmind_database_client.download_zip_file(
            location_type=location_type
        )
        file_processor = MaxmindFileProcessor(location_type=location_type)
        file_processor.load_zip_file_data_to_db(zip_file=zip_file)

    def handle_city_data(self):
        """
        Checks the date for the last added city data against
        the date of the last modified maxmind data
        Updates the db if there is newer city data from maxmind
        """
        city_location_type = "city"
        last_maxmind_city_date = self.maxmind_database_client.get_last_modified_date(
            location_type=city_location_type
        )
        log.info(f"Last modified Maxmind city data date {last_maxmind_city_date}")
        last_city_data = self.get_last_location_data(location_type=city_location_type)
        if not last_city_data:
            self.load_maxmind_data(location_type=city_location_type)
        elif (
            last_city_data and date_parser(last_maxmind_city_date) > last_city_data.date
        ):
            self.load_maxmind_data(location_type=city_location_type)

    def handle_country_data(self):
        """
        Checks the date for the last added country data against
        the date of the last modified maxmind data
        Updates the db if there is newer country data from maxmind
        """
        country_location_type = "country"
        last_maxmind_country_date = self.maxmind_database_client.get_last_modified_date(
            location_type=country_location_type
        )
        log.info(f"Last modified Maxmind country data date {last_maxmind_country_date}")
        last_country_data = self.get_last_location_data(
            location_type=country_location_type
        )
        if not last_country_data:
            self.load_maxmind_data(location_type=country_location_type)
        elif (
            last_country_data
            and date_parser(last_maxmind_country_date) > last_country_data.date
        ):
            self.load_maxmind_data(location_type=country_location_type)
