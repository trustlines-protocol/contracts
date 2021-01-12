import eth_tester.exceptions
import pytest

from tests.conftest import get_single_event_of_contract


def test_implementation_set(proxy_beacon, upgradeable_implementation):
    assert (
        proxy_beacon.functions.implementation().call()
        == upgradeable_implementation.address
    )


def test_update_implementation(proxy_beacon, upgraded_implementation, owner):
    proxy_beacon.functions.upgradeTo(upgraded_implementation.address).transact(
        {"from": owner}
    )
    assert (
        proxy_beacon.functions.implementation().call()
        == upgraded_implementation.address
    )


def test_update_implementation_not_owner(
    proxy_beacon, upgraded_implementation, not_owner
):
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        proxy_beacon.functions.upgradeTo(upgraded_implementation.address).transact(
            {"from": not_owner}
        )


def test_update_implementation_event(proxy_beacon, upgraded_implementation, owner):
    proxy_beacon.functions.upgradeTo(upgraded_implementation.address).transact(
        {"from": owner}
    )
    upgraded_event = get_single_event_of_contract(proxy_beacon, "Upgraded")
    assert upgraded_event["args"]["implementation"] == upgraded_implementation.address
