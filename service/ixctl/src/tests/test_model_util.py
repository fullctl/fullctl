import pytest
from django.conf import settings
from django_ixctl.models import InternetExchangeMember
from django_ixctl.models.util import set_port_fields_from_speed


class TestSetPortFieldsFromSpeed:
    @pytest.mark.parametrize(
        "speed,expected_size,expected_quantity,expected_lag",
        [
            # Normal cases - each should use smallest port size that can handle the speed
            (1000, 1, 1, False),  # 1G -> 1x1G port
            (10000, 10, 1, False),  # 10G -> 1x10G port
            (20000, 10, 2, True),  # 20G -> 2x10G ports
            (100000, 100, 1, False),  # 100G -> 1x100G port
            (150000, 100, 2, True),  # 150G -> 2x100G ports
            # Edge cases
            (0, 1, 1, False),  # Zero speed
            (None, 1, 1, False),  # None speed
            (15000, 10, 2, True),  # 15G -> 2x10G ports (rounded up)
            # Boundary cases
            (1100, 10, 1, False),  # 1.1G -> 1x10G port (not 2x1G)
            (9900, 10, 1, False),  # 9.9G -> 1x10G port
            (11000, 10, 2, True),  # 11G -> 2x10G ports
        ],
    )
    def test_port_field_calculations(
        self, speed, expected_size, expected_quantity, expected_lag
    ):
        """
        Test that port fields are correctly calculated for various speeds,
        always selecting the smallest port size that can handle the speed
        within the max port quantity limit.
        """
        member = InternetExchangeMember()

        set_port_fields_from_speed(member, speed)

        assert (
            member.port_size == expected_size
        ), f"Speed {speed}Mb should result in port size of {expected_size}Gb"
        assert (
            member.port_quantity == expected_quantity
        ), f"Speed {speed}Mb should result in {expected_quantity} ports"
        assert (
            member.lag == expected_lag
        ), f"Speed {speed}Mb should result in LAG being {expected_lag}"

    def test_exceeds_max_ports(self):
        """
        Test that function handles speeds that would exceed maximum port quantity
        """
        # Arrange
        member = InternetExchangeMember()

        # Act
        set_port_fields_from_speed(member, 1000000)

        # Assert
        assert (
            member.port_quantity <= settings.PORT_LIMIT_MAX
        ), "Port quantity should not exceed PORT_LIMIT_MAX"
        assert (
            member.port_size == 100
        ), "Should use largest available port size for very high speeds"
        assert member.lag is True, "Should enable LAG when using multiple ports"

    @pytest.mark.parametrize(
        "speed,error_expected",
        [
            (-1000, ValueError),
        ],
    )
    def test_invalid_inputs(self, speed, error_expected):
        """Test that function properly handles invalid inputs"""
        member = InternetExchangeMember()

        with pytest.raises(error_expected):
            set_port_fields_from_speed(member, speed)
