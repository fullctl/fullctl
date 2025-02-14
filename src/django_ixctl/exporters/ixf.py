import datetime
import json


def normalize_member_type_v1(member_type: str) -> str:
    """
    IX-F schema v1.0 only supports peering, ixp and other

    Any invalid type should be changed to "other"
    """
    if member_type in ["peering", "ixp"]:
        return member_type
    return "other"


def export(ix, pretty=False):
    member_list = []

    rv = {
        "version": "1.0",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "member_list": member_list,
        "ixp_list": [{"ixp_id": ix.id, "shortname": ix.name, "ixf_id": ix.ixf_id or 0}],
    }

    for ix in [ix]:
        asns = []
        for member in ix.member_set.all():
            if member.asn in asns:
                continue
            connection_list = []
            member_dict = {
                "asnum": member.asn,
                "member_type": normalize_member_type_v1(member.ixf_member_type),
                "connection_list": connection_list,
            }
            member_list.append(member_dict)
            asns.append(member.asn)
            for _member in ix.member_set.filter(asn=member.asn):
                vlan_list = [{}]
                connection = {
                    "ixp_id": _member.ix.id,
                    "state": _member.ixf_state,
                    "if_list": [{"if_speed": _member.speed}],
                    "vlan_list": vlan_list,
                }
                connection_list.append(connection)

                if _member.ipaddr4:
                    vlan_list[0]["ipv4"] = {
                        "address": f"{_member.ipaddr4}",
                        "routeserver": _member.is_rs_peer,
                    }
                if _member.ipaddr6:
                    vlan_list[0]["ipv6"] = {
                        "address": f"{_member.ipaddr6}",
                        "routeserver": _member.is_rs_peer,
                    }

    if pretty:
        return json.dumps(rv, indent=2)
    else:
        return json.dumps(rv)
