from django.conf import settings

__all__ = [
    "set_port_fields_from_speed",
]

def set_port_fields_from_speed(member, speed:int):
    """
    Will update port_size, lag and port_quantity based on the speed
    on an InternetExchangeMember object
    
    Arguments:

    - member: InternetExchangeMember object
    - speed: int, speed in Mb
    """
    max_port_quantity = settings.PORT_LIMIT
    port_sizes = sorted(settings.PORT_SIZES, reverse=True)

    if speed is None or speed == 0:
        member.port_size = 1
        member.port_quantity = 1
    else:
        port_size = min(port_sizes)
        for size in port_sizes:
            if (member.speed / 1000) < size * max_port_quantity:
                port_size = size
        member.port_size = port_size
        member.port_quantity = speed / (port_size * 1000)

        # port quantity is an integer, so round up if necessary
        if member.port_quantity % 1 != 0:
            member.port_quantity = int(member.port_quantity) + 1
        else:
            member.port_quantity = int(member.port_quantity)

        member.lag = member.port_quantity > 1