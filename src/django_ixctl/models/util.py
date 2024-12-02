from django.conf import settings

__all__ = [
    "set_port_fields_from_speed",
]


def set_port_fields_from_speed(member, speed: int):
    """
    Will update port_size, lag and port_quantity based on the speed
    on an InternetExchangeMember object.

    Arguments:
    - member: InternetExchangeMember object
    - speed: int, speed in Mb
    """
    max_port_quantity = settings.PORT_LIMIT_MAX
    port_sizes = sorted(settings.PORT_SIZES, reverse=True)  # [100, 10, 1]

    if speed is None or speed == 0:
        member.port_size = 1
        member.port_quantity = 1
        member.lag = False
        return


    if speed < 0:
        raise ValueError("Speed must be a positive integer")

    speed_in_gb = speed / 1000
    
    # Start from smallest port size
    for size in reversed(port_sizes):  # [1, 10, 100]
        ports_needed = speed_in_gb / size
        # Use this size if:
        # 1. We need exactly 1 port OR
        # 2. We need more than 1 port but less than max_ports AND this is the largest possible size
        if ports_needed <= 1 or (ports_needed <= max_port_quantity and size >= ports_needed):
            member.port_size = size
            member.port_quantity = int(ports_needed + 0.999)  # Round up
            break
    else:
        # If no size works within max_port_quantity, use the largest size
        member.port_size = port_sizes[0]
        member.port_quantity = min(int(speed_in_gb / port_sizes[0] + 0.999), max_port_quantity)

    member.lag = member.port_quantity > 1