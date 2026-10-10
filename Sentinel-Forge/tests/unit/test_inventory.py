import pytest
from pydantic import ValidationError

from sentinelforge.config import Settings
from sentinelforge.inventory import Inventory, load_inventory


@pytest.fixture(scope="module")
def inventory():
    return load_inventory(Settings().inventory_path)


def test_inventory_loads(inventory):
    assert inventory.identities
    assert inventory.assets
    assert inventory.organisation


def test_lookup_helpers(inventory):
    assert inventory.identities_by_user["adm.sam"].privileged
    assert inventory.assets_by_host["srv-dc-01"].criticality == "critical"


def test_is_internal(inventory):
    assert inventory.is_internal("10.20.1.11")
    assert not inventory.is_internal("203.0.113.5")
    assert not inventory.is_internal(None)


def test_is_privileged(inventory):
    assert inventory.is_privileged("adm.sam")
    assert not inventory.is_privileged("alice.lab")
    assert not inventory.is_privileged(None)


def test_criticality_defaults_to_medium_for_unknown_host(inventory):
    assert inventory.criticality("does-not-exist") == "medium"
    assert inventory.criticality("srv-dc-01") == "critical"


def test_shared_infrastructure(inventory):
    assert inventory.is_shared_infrastructure("srv-vpn-01")
    assert inventory.is_shared_infrastructure("fw-edge-01")
    assert not inventory.is_shared_infrastructure("ws-fin-01")


def test_business_hours(inventory):
    assert inventory.is_business_hour(10)
    assert not inventory.is_business_hour(3)


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        Inventory.model_validate(
            {
                "organisation": "x",
                "business_hours_utc": {"start": 8, "end": 18},
                "internal_networks": ["10.0.0.0/8"],
                "privileged_groups": [],
                "authorised_admins": [],
                "identities": [],
                "assets": [],
                "surprise": 1,
            }
        )


def test_invalid_network_is_rejected():
    with pytest.raises(ValidationError):
        Inventory.model_validate(
            {
                "organisation": "x",
                "business_hours_utc": {"start": 8, "end": 18},
                "internal_networks": ["not-a-network"],
                "privileged_groups": [],
                "authorised_admins": [],
                "identities": [],
                "assets": [],
            }
        )
