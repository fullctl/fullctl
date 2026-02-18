"""
Implements querying and normalizing APNIC Whowas (historical RDAP) data.

APNIC provides historical RDAP data through their /history/ip/{prefix} endpoint.
"""
import structlog

import rdap
import rdap.exceptions

from prefix_meta.models import Data, Request

__all__ = [
    "ApnicWhowasData",
    "ApnicWhowasRequest",
]

logger = structlog.get_logger(__name__)


class ApnicWhowasData(Data):
    """
    APNIC Whowas data
    """

    class Meta:
        proxy = True

    class Config(Data.Config):
        source_name = "apnic-whowas"
        type = "whowas"

    @classmethod
    def get_prefix_queryset(cls, prefix):
        return (
            super()
            .get_prefix_queryset(prefix)
            .filter(type=cls.config("type"), source_name=cls.config("source_name"))
        )

    @property
    def history_records(self):
        """
        Returns all historical records from the data.
        Each record contains timestamp ranges and RDAP data.
        """
        return self.data.get("records", [])

    def get_records_by_handle(self, handle):
        """
        Filter historical records by handle (IP range).

        Args:
            handle: IP range handle (e.g., "101.203.88.0 - 101.203.95.255")

        Returns:
            List of historical records matching the handle
        """
        return [
            record
            for record in self.history_records
            if record.get("handle") == handle
        ]

    def get_most_specific_records(self):
        """
        Returns only the records for the most specific (smallest) IP block.
        Filters out parent/larger allocations.
        """
        if not self.history_records:
            return []

        # Find current record (most recent without end date)
        current_records = [
            r for r in self.history_records if r.get("applicable_until") is None
        ]

        if not current_records:
            # If no current, use the most recent
            sorted_records = sorted(
                self.history_records,
                key=lambda r: r.get("applicable_from", ""),
                reverse=True,
            )
            current_records = [sorted_records[0]] if sorted_records else []

        if current_records:
            most_specific_handle = current_records[0].get("handle")
            return self.get_records_by_handle(most_specific_handle)

        return []


class ApnicWhowasRequest(Request):
    """
    APNIC Whowas request handler
    """

    class Meta:
        proxy = True

    class Config(Request.Config):
        source_name = "apnic-whowas"
        meta_data_cls = ApnicWhowasData
        max_prefixlen_4 = 10
        max_prefixlen_6 = 32
        min_prefixlen_4 = 32
        min_predixlen_6 = 128

        # Cache for a day
        cache_expiry = 86400

        # Filter mode: "all", "most_specific", or a specific handle
        filter_mode = "most_specific"

    @classmethod
    def target_to_url(cls, target):
        return f"APNIC Whowas {target}"

    @classmethod
    def target_to_type(cls, target):
        return "live"

    @classmethod
    def send(cls, target):
        url = cls.target_to_url(target)
        logger.debug(f"sending APNIC whowas request to {url} - target - {target}")
        data = cls.whowas_request(target)
        return cls.process(target, url, 200, data)

    @classmethod
    def whowas_request(cls, target):
        """
        Request historical RDAP data from APNIC.

        Args:
            target: IP address or prefix to query

        Returns:
            Dictionary containing historical records
        """
        client = rdap.RdapClient(config={"ignore_recurse_errors": True})

        try:
            history = client.get_ip_history(target)
        except rdap.exceptions.RdapNotFoundError:
            logger.warning(f"APNIC whowas not found for {target}")
            return {"records": []}
        except rdap.exceptions.RdapHTTPError as e:
            logger.error(f"APNIC whowas HTTP error for {target}: {e}")
            return {"records": []}

        processed_records = []

        filter_mode = cls.config("filter_mode")

        if filter_mode == "most_specific":
            records_to_process = history.get_most_specific_records()
        elif filter_mode == "all":
            records_to_process = history.records
        else:
            records_to_process = history.filter_by_handle(filter_mode)

        for record in records_to_process:
            content = record.content

            if not content:
                continue

            record_data = {
                "applicable_from": record.applicable_from,
                "applicable_until": record.applicable_until,
                "is_current": record.is_current,
                "handle": record.handle,
            }

            try:
                record_data["org_name"] = content.org_name
            except (KeyError, AttributeError):
                pass

            try:
                record_data["org_address"] = content.org_address
            except (KeyError, AttributeError):
                pass

            try:
                record_data["name"] = content.name
            except (KeyError, AttributeError):
                pass

            try:
                record_data["country"] = content.data.get("country")
            except (KeyError, AttributeError):
                pass

            try:
                record_data["emails"] = content.emails
            except (KeyError, AttributeError):
                pass

            events = content.data.get("events", [])
            for event in events:
                if event["eventAction"] == "last changed":
                    record_data["last_changed"] = event["eventDate"]
                elif event["eventAction"] == "registration":
                    record_data["registration"] = event["eventDate"]

            rir_name = content.get_rir()
            record_data["source"] = rir_name.upper() if rir_name else "APNIC"

            processed_records.append(record_data)

        processed_records.sort(
            key=lambda r: r.get("applicable_from", ""), reverse=True
        )

        return {"records": processed_records}


