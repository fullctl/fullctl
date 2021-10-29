import django_peeringdb.models.concrete as pdb_models
from fullctl.django.models import AuditLog


def count(model):
    return {model.HandleRef.tag: model.objects.filter(status="ok").count()}


def last_sync():

    qset = AuditLog.objects.filter(action="command", info__contains="peeringdb_sync")
    cmd = qset.order_by("-created").first()
    return cmd


def stats():

    r = {}
    r.update(count(pdb_models.Organization))
    r.update(count(pdb_models.Network))
    r.update(count(pdb_models.Facility))
    r.update(count(pdb_models.InternetExchange))
    r.update(count(pdb_models.NetworkIXLan))
    r.update(count(pdb_models.NetworkContact))
    r.update(count(pdb_models.NetworkFacility))
    r.update(count(pdb_models.IXLanPrefix))
    r.update(count(pdb_models.IXLan))
    r.update(count(pdb_models.InternetExchangeFacility))
    return r
