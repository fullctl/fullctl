import django_ixctl.exporters.ixf
from django.conf import settings
from django.db.models import Prefetch
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django_ixctl.context_processors import check_trial_available
from django_ixctl.models import (
    InternetExchange,
    InternetExchangeMember,
    NetworkMeta,
    Routeserver,
)
from django_ixctl.rest.decorators import load_instance_ix, require_auth_ix

from fullctl.django.decorators import load_instance, require_auth

# Create your views here.


def make_env(request, **kwargs):
    r = {"env": settings.RELEASE_ENV, "version": settings.PACKAGE_VERSION}
    r.update(**kwargs)
    return r


@require_auth()
@load_instance()
def view_instance(request, instance, **kwargs):
    env = make_env(request, instance=instance, org=instance.org)

    env["select_ix"] = InternetExchange.get_default_exchange_for_org(instance.org)
    if env["select_ix"]:
        env.update(check_trial_available(request.org.slug, env["select_ix"].slug))

    return render(request, "theme-select.html", env)


@require_auth_ix()
@load_instance_ix()
def view_instance_load_ix(request, instance, ix_tag, **kwargs):
    try:
        ix = InternetExchange.objects.prefetch_related(
            "member_set",
            Prefetch(
                "rs_set",
                queryset=Routeserver.objects.select_related("routeserverconfig").all(),
            ),
        ).get(instance=instance, slug=ix_tag)
    except InternetExchange.DoesNotExist:
        raise Http404

    env = make_env(request, instance=instance, org=instance.org)
    env["select_ix"] = ix
    env.update(check_trial_available(request.org.slug, ix.slug))

    members = ix.member_set.all().order_by("name")
    InternetExchangeMember.preload_network_meta(instance.org, members)
    env["members"] = members

    if ix.public_view and not request.user.is_authenticated:
        return render(request, "ixctl/v2/tool/information/public_main.html", env)
    return render(request, "theme-select.html", env)


@require_auth()
@load_instance(public=True)
def public_view_redirect(request, instance, ix_tag, **kwargs):
    try:
        ix = InternetExchange.objects.prefetch_related(
            "member_set",
            Prefetch(
                "rs_set",
                queryset=Routeserver.objects.select_related("routeserverconfig").all(),
            ),
        ).get(instance=instance, slug=ix_tag)
    except InternetExchange.DoesNotExist:
        raise Http404

    env = make_env(request, instance=instance, org=instance.org)
    env["select_ix"] = ix

    members = ix.member_set.all().order_by("name")
    InternetExchangeMember.preload_network_meta(instance.org, members)
    env["members"] = members

    return render(request, "ixctl/v2/tool/information/public_main.html", env)


@require_auth()
def org_redirect(request):
    return redirect(f"/{request.org.slug}/")


@load_instance(public=True)
def export_ixf(request, instance, ix_tag, **kwargs):
    try:
        ix = InternetExchange.objects.get(instance=instance, slug=ix_tag)
    except InternetExchange.DoesNotExist:
        raise Http404

    # Handle private
    if ix.ixf_export_privacy == "private":
        if request.GET.get("secret") != ix.urlkey:
            raise Http404

    if "pretty" in request.GET:
        pretty = True
    else:
        pretty = False

    rv = django_ixctl.exporters.ixf.export(ix, pretty=pretty)
    return HttpResponse(rv, content_type="application/json")


@load_instance(public=True)
def export_ixp_manager(request, instance, ix_tag, **kwargs):
    """Return an aggregated member list as JSON, one entry per network.

    ixctl stores one *member* record per logical port/IP-pair.  A single
    network that has multiple interfaces (dual-stack addresses or multiple
    physical connections/LAG members) will therefore have several
    `InternetExchangeMember` rows.

    The logic below iterates over **all** members of the IX, groups them
    by ASN and builds one consolidated dictionary per network:

    • numberofports - summed across all member rows.
    • rs - "Yes" if *any* of the member rows is marked as a route-server peer.
    • ipv4 / ipv6 - space separated list of all addresses belonging to that
      ASN (order preserved by queryset ordering).
    • ports - space separated list where each element is either
      "<speed>" (single port) or "<qty>*<speed>" (LAG).  Speeds are converted
      from Gb stored in the DB to Mb.

    Meta-data (URL, logo, policies, etc.) is taken from the first member row
    - because these attributes are per-network in practice.
    """

    try:
        ix = (
            InternetExchange.objects.select_related("instance")
            .prefetch_related(
                "member_set",
                "member_set__ix",
                "member_set__mac_addresses",
            )
            .get(instance=instance, slug=ix_tag)
        )
    except InternetExchange.DoesNotExist:
        raise Http404

    # Optional secret check - controlled through ix.urlkey and query param `secret`
    # TODO: this currently piggybacks on the existing ixf_export_privacy setting, which should likely
    # be renamed to a more general "export_privacy" setting.
    if ix.ixf_export_privacy == "private":
        if request.GET.get("secret") != ix.urlkey:
            raise Http404

    aggregated: dict[int, dict] = {}

    InternetExchangeMember.preload_network_meta(instance.org, ix.member_set.all())

    for member in ix.member_set.all().order_by("name"):
        try:
            net_meta = getattr(member, "network_meta", None)
        except NetworkMeta.DoesNotExist:
            net_meta = None

        asn = member.asn

        # Build ports string for this member
        if member.port_quantity and member.port_size:
            if member.port_quantity == 1:
                member_ports_str = f"{member.port_size * 1000}"
            else:
                member_ports_str = f"{member.port_quantity}*{member.port_size * 1000}"
        else:
            member_ports_str = ""

        custom = {}
        if isinstance(member.meta, dict):
            custom = member.meta.get("custom", {}) or {}

        # Initialize aggregate entry if not exists
        if asn not in aggregated:
            aggregated[asn] = {
                "type": custom.get("type"),
                "url": getattr(net_meta, "web_url", None),
                "name": member.name,
                "numberofports": 0,
                "joined": custom.get("joined"),
                "logo": getattr(net_meta, "logo_url", None),
                "asnum": asn,
                "peeringpolicy": custom.get("peeringpolicy"),
                "rs": "No",
                "ipv4": [],
                "ipv6": [],
                "ports": [],
                "reseller": custom.get("reseller", ""),
                "resold": custom.get("resold", ""),
            }

        agg = aggregated[asn]

        # Update aggregate fields
        agg["numberofports"] += member.port_quantity or 0
        if member.is_rs_peer:
            agg["rs"] = "Yes"

        # Append addresses and ports
        if member.ipaddr4:
            agg["ipv4"].append(str(member.ipaddr4).strip())
        if member.ipaddr6:
            agg["ipv6"].append(str(member.ipaddr6).strip())
        if member_ports_str:
            agg["ports"].append(member_ports_str)

    # Convert aggregated to list with concatenated strings
    members_json = []
    for agg in aggregated.values():
        agg["ipv4"] = " ".join(agg["ipv4"]).strip()
        agg["ipv6"] = " ".join(agg["ipv6"]).strip()
        agg["ports"] = " ".join(agg["ports"]).strip()
        members_json.append(agg)

    # Compose final structure - following the same outer structure as example list.json
    response_payload = {
        "member_list": members_json,
        "member_count": len(members_json),
    }

    import json

    indent = 4 if "pretty" in request.GET else None

    return HttpResponse(
        json.dumps(response_payload, indent=indent),
        content_type="application/json",
    )
