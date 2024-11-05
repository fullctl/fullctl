from django_ixctl.models.ixctl import InternetExchange
from django_ixctl.port_automation import get_ix_lan_config


def test_get_ix_lan_config_no_overrides(db, pdb_data, account_objects):
    ix = account_objects.ix

    ix.mtu = None
    ix.prefixes.all().delete()
    ix.pdb_id = 239
    ix.save()

    # test from peeringdb
    config = get_ix_lan_config(ix)
    assert config.model_dump() == {
        "mtu": 9000,
        "prefixes": ["206.41.110.0/24", "2001:504:41:110::/64"],
    }


def test_get_ix_lan_config_with_overrides(db, pdb_data, account_objects):
    ix = account_objects.ix

    ix.mtu = 1500
    ix.prefixes.all().delete()

    ix.prefixes.create(prefix="10.10.10.0/24")

    config = get_ix_lan_config(ix)

    assert config.model_dump() == {"mtu": 1500, "prefixes": ["10.10.10.0/24"]}


def test_get_ix_lan_config_no_overrides_no_peeringdb(db, pdb_data, account_objects):
    ix = account_objects.ix

    ix.mtu = None
    ix.prefixes.all().delete()
    ix.pdb_id = None
    ix.save()

    config = get_ix_lan_config(ix)
    assert config.model_dump() == {"mtu": None, "prefixes": []}


def test_get_ix_lan_config_no_overrides_invalid_peeringdb(
    db, pdb_data, account_objects
):
    ix = InternetExchange.objects.create(
        instance=account_objects.ixctl_instance, pdb_id=404, mtu=None
    )

    assert ix.mtu is None
    assert ix.prefixes.count() == 0
    assert ix.pdb_id == 404

    config = get_ix_lan_config(ix)
    assert config.model_dump() == {"mtu": None, "prefixes": []}
