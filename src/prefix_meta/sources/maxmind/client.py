import csv
import os
import tempfile
from datetime import datetime
from io import BytesIO
from zipfile import ZipFile

import requests
import structlog
from django.conf import settings

from prefix_meta.sources.maxmind.models import (
    MaxmindLocationData,
    MaxmindLocationsReferenceData,
)

MAXMIND_DATABASE_URL = getattr(settings, "MAXMIND_DATABASE_URL")
MAXMIND_DATABASE_FOLDER_NAME_PREFIX = getattr(
    settings, "MAXMIND_DATABASE_FOLDER_NAME_PREFIX"
)
MAXMIND_BATCH_CHUNK_SIZE = getattr(settings, "MAXMIND_BATCH_CHUNK_SIZE")


log = structlog.get_logger("django")


class MaxmindDatabaseClient:
    """
    Maxmind Database Client
    Handles downloading the database based on the location i.e. city, country
    """

    def __init__(self, account_id, api_key):
        self.base_url = self.build_url()
        self.api_key = api_key
        self.account_id = account_id
        self.auth = (self.account_id, self.api_key)

    def build_url(self):
        return (
            f"{MAXMIND_DATABASE_URL}/{MAXMIND_DATABASE_FOLDER_NAME_PREFIX}"
            + "-{location_type}-CSV/download?suffix=zip"
        )

    def get_url(self, location_type: str) -> str:
        """
        Returns the url formatted with the location type i.e. city or country
        """
        return self.base_url.format(location_type=location_type.capitalize())

    def get_last_modified_date(self, location_type: str) -> str:
        """
        Returns the last modified date of the database
        """
        response = requests.head(self.get_url(location_type), auth=self.auth)
        return response.headers.get("Last-Modified")

    def download_zip_file(self, location_type: str) -> BytesIO:
        """
        Returns the database zip file
        """
        response = requests.get(
            self.get_url(location_type), auth=self.auth, allow_redirects=True
        )
        response.raise_for_status()
        return BytesIO(response.content)


class MaxmindFileProcessor:
    """
    Maxmind File Processor processes the maxmind database zip file
    """

    def __init__(self, location_type: str):
        self.location_type = location_type
        self.expected_file_names = [
            f"{MAXMIND_DATABASE_FOLDER_NAME_PREFIX}-{self.location_type.capitalize()}-Blocks-IPv4.csv",
            f"{MAXMIND_DATABASE_FOLDER_NAME_PREFIX}-{self.location_type.capitalize()}-Blocks-IPv6.csv",
            f"{MAXMIND_DATABASE_FOLDER_NAME_PREFIX}-{self.location_type.capitalize()}-Locations-en.csv",
        ]

    def extract_zip_file(self, zip_file: BytesIO, temp_dir: str):
        """
        Extracts the zip file and returns the allowed database file names
        """
        with ZipFile(zip_file) as z:
            z.extractall(temp_dir)
            return [
                os.path.join(temp_dir, name)
                for name in z.namelist()
                if name.split("/")[-1] in self.expected_file_names
            ]

    def read_csv_to_db(self, file_paths: list[str]):
        """
        Reads the csv file and to the database
        """
        for file_path in file_paths:
            if (
                f"{MAXMIND_DATABASE_FOLDER_NAME_PREFIX}-{self.location_type.capitalize()}-Locations-en.csv"
                not in file_path
            ):
                self.load_locations_data(file_path=file_path)
            else:
                self.load_locations_reference_data(file_path=file_path)

    def load_locations_reference_data(self, file_path: str):
        """
        Checks for existing locations reference data in the db
        from the csv and updates it or
        creates a new location reference if none exists
        """
        with open(file_path, encoding="utf-8") as f:
            bulk_update_data = []
            bulk_update_fields = ["data"]
            for row in csv.DictReader(f):
                if existing_data := MaxmindLocationsReferenceData.objects.filter(
                    geoname_id=row.get("geoname_id")
                ).first():
                    existing_data.data = row
                    bulk_update_data.append(existing_data)
                else:
                    try:
                        MaxmindLocationsReferenceData(
                            geoname_id=row.get("geoname_id"), data=row
                        ).save()
                    except Exception as ex:
                        log.exception(
                            f"The following exception occurred while saving {self.location_type} location reference data {row}:\n{str(ex)}"
                        )

                if len(bulk_update_data) == MAXMIND_BATCH_CHUNK_SIZE:
                    self.bulk_update_location_reference_data(
                        bulk_update_data=bulk_update_data,
                        bulk_update_fields=bulk_update_fields,
                    )
                    bulk_update_data = []

            if len(bulk_update_data):
                self.bulk_update_location_reference_data(
                    bulk_update_data=bulk_update_data,
                    bulk_update_fields=bulk_update_fields,
                )

    def bulk_update_location_reference_data(
        self,
        bulk_update_data: list[MaxmindLocationsReferenceData],
        bulk_update_fields: list[str],
    ):
        try:
            MaxmindLocationsReferenceData.objects.bulk_update(
                bulk_update_data, fields=bulk_update_fields
            )
        except Exception as ex:
            data = [update_data.data for update_data in bulk_update_data]
            log.exception(
                f"The following exception occurred while bulk updating {self.location_type} location reference data {data}:\n{str(ex)}"
            )

    def load_locations_data(self, file_path: str):
        """
        Checks for existing locations data in the db
        from the csv and updates it or
        creates a new location data if none exists
        """
        now = datetime.now()

        with open(file_path, encoding="utf-8") as f:
            bulk_update_data = []
            bulk_update_fields = ["data", "date", "geoname_id"]
            for row in csv.DictReader(f):
                params = {
                    "prefix": row.get("network"),
                    "source_name": "maxmind",
                    "type": "location",
                    "location_type": self.location_type.lower(),
                }
                if (
                    existing_data := MaxmindLocationData.objects.filter(**params)
                    .order_by("-date")
                    .first()
                ):
                    existing_data.data = row
                    existing_data.geoname_id = row.get("geoname_id") or row.get(
                        "registered_country_geoname_id"
                    )
                    existing_data.date = now
                    bulk_update_data.append(existing_data)
                else:
                    try:
                        MaxmindLocationData(
                            **params,
                            data=row,
                            geoname_id=row.get("geoname_id")
                            or row.get("registered_country_geoname_id"),
                            date=now,
                        ).save()
                    except Exception as ex:
                        log.exception(
                            f"The following exception occurred while saving {self.location_type} data {row}:\n{str(ex)}"
                        )

                if len(bulk_update_data) == MAXMIND_BATCH_CHUNK_SIZE:
                    self.bulk_update_location_data(
                        bulk_update_data=bulk_update_data,
                        bulk_update_fields=bulk_update_fields,
                    )
                    bulk_update_data = []

            if len(bulk_update_data):
                self.bulk_update_location_data(
                    bulk_update_data=bulk_update_data,
                    bulk_update_fields=bulk_update_fields,
                )

    def bulk_update_location_data(
        self, bulk_update_data: list[MaxmindLocationData], bulk_update_fields: list[str]
    ):
        try:
            MaxmindLocationData.objects.bulk_update(
                bulk_update_data, fields=bulk_update_fields
            )
        except Exception as ex:
            data = [update_data.data for update_data in bulk_update_data]
            log.exception(
                f"The following exception occurred while bulk updating {self.location_type} data {data}:\n{str(ex)}"
            )

    def load_zip_file_data_to_db(self, zip_file: BytesIO):
        """
        Main method that processes the zip file data to the db
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            file_paths = self.extract_zip_file(zip_file=zip_file, temp_dir=temp_dir)
            self.read_csv_to_db(file_paths)
