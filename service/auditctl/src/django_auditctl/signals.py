from django.db.models.signals import post_save
from django.dispatch import receiver

import django_auditctl.models as auditctl_models
from django_auditctl.models.tasks import ExecuteEventHandler


@receiver(post_save, sender=auditctl_models.Event)
def handle_audit_event(sender, instance, created, **kwargs):
    if created:
        ExecuteEventHandler.create_tasks(instance)