from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in

from fullctl.django.util import (
    create_personal_org,
)

@receiver(user_logged_in)
def handle_login(sender, **kwargs):
    user = kwargs.get("user")
    create_personal_org(user)
    #XXX: move to create_personal_org signal
    #create_networks_from_verified_asns(user)
