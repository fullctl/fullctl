import ipaddress

import pydantic

__all__ = [
    "OrganizationConfig",
    "TrafficPeriod",
]


class TrafficPeriod(pydantic.BaseModel):
    """
    Defines a period of time over which traffic is aggregated
    into a PNG visualization.
    """

    duration: int
    resolution: int
    filename_suffix: str


def default_periods() -> list[TrafficPeriod]:
    """
    Defines the default traffic periods.
    """
    return [
        TrafficPeriod(duration=86400, resolution=300, filename_suffix="5m"),
        TrafficPeriod(duration=86400 * 7, resolution=1800, filename_suffix="30m"),
        TrafficPeriod(duration=86400 * 30, resolution=7200, filename_suffix="2h"),
        TrafficPeriod(duration=86400 * 365, resolution=86400, filename_suffix="1d"),
    ]


class OrganizationConfig(pydantic.BaseModel):
    """
    Defines the configuration for an organization.
    """

    traffic_periods: list[TrafficPeriod] = pydantic.Field(
        default_factory=default_periods
    )

    @property
    def traffic_periods_as_tuples(self) -> list[tuple[int, int, str]]:
        """
        Returns the traffic periods as a list of tuples.
        """
        return [
            (period.duration, period.resolution, period.filename_suffix)
            for period in self.traffic_periods
        ]
