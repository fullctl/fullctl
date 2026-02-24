from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_ixctl.models import InternetExchangeMember, Routeserver
from django_ixctl.util import create_networks_from_verified_asns

from fullctl.django.models.concrete.tasks import TaskLimitError


@receiver(user_logged_in)
def handle_login(sender, **kwargs):
    user = kwargs.get("user")
    create_networks_from_verified_asns(user)


# update RouteserverConfigs of Internet Exchange when InternetExchangeMember is updated
@receiver(post_save, sender=InternetExchangeMember)
def update_routeserver(sender, instance, **kwargs):
    internet_exchange = instance.ix
    routeservers = Routeserver.objects.filter(ix=internet_exchange)
    for routeserver in routeservers:
        try:
            routeserver.routeserver_config.queue_generate()
        except TaskLimitError:
            pass
