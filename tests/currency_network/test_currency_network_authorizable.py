#! pytest

import pytest

import eth_tester.exceptions

from tests.conftest import CurrencyNetworkAdapter
from tests.currency_network.conftest import deploy_test_network, NETWORK_SETTING

SECONDS_PER_YEAR = 60 * 60 * 24 * 365

trustlines = [(1, 2, 100, 150)]


@pytest.fixture(scope="session")
def global_authorized_address(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def currency_network_contract_authorized_with_trustlines(
    web3, global_authorized_address, accounts
):
    network_setting = {**NETWORK_SETTING, "fee_divisor": 100, "custom_interests": True}
    contract = deploy_test_network(
        web3, network_setting, authorized_addresses=[global_authorized_address]
    )

    for (A, B, clAB, clBA) in trustlines:
        CurrencyNetworkAdapter(contract).set_account(
            accounts[A], accounts[B], creditline_given=clAB, creditline_received=clBA
        )
    return contract


@pytest.fixture(scope="session")
def possible_transfer_path(accounts):
    first_trustline = trustlines[0]
    return [accounts[first_trustline[0]], accounts[first_trustline[1]]]


@pytest.fixture(scope="session")
def currency_network_adapter(currency_network_contract_authorized_with_trustlines):
    return CurrencyNetworkAdapter(currency_network_contract_authorized_with_trustlines)


def test_transfer_from_global_authorized(
    currency_network_adapter, global_authorized_address, possible_transfer_path
):
    currency_network_adapter.transfer_from(
        global_authorized_address, 1, path=possible_transfer_path
    )


def test_transfer_from_not_authorized(
    currency_network_adapter,
    global_authorized_address,
    accounts,
    possible_transfer_path,
):
    assert accounts[1] != global_authorized_address
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        currency_network_adapter.transfer_from(
            accounts[1], 1, path=possible_transfer_path
        )


def test_transfer_from_personal_authorized(
    currency_network_adapter, possible_transfer_path, accounts
):
    authorized_address = accounts[3]
    currency_network_adapter.add_authorized_address(
        target=authorized_address, sender=possible_transfer_path[0]
    )
    currency_network_adapter.transfer_from(
        authorized_address, 1, path=possible_transfer_path
    )


def test_transfer_from_removed_personal_authorized(
    currency_network_adapter, possible_transfer_path, accounts
):
    authorized_address = accounts[3]
    sender = possible_transfer_path[0]
    currency_network_adapter.add_authorized_address(
        target=authorized_address, sender=sender
    )
    currency_network_adapter.remove_authorized_address(
        target=authorized_address, sender=sender
    )
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        currency_network_adapter.transfer_from(
            authorized_address, 1, path=possible_transfer_path
        )


def test_cannot_remove_not_authorized(currency_network_adapter, accounts):
    target = accounts[3]
    sender = accounts[4]
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        currency_network_adapter.remove_authorized_address(target=target, sender=sender)


def test_add_global_authorized_event(
    currency_network_adapter, global_authorized_address
):
    global_authorized_events = currency_network_adapter.events(
        "GlobalAuthorizedAddressAdd"
    )
    assert len(global_authorized_events) == 1
    assert (
        global_authorized_events[0]["args"]["authorized"] == global_authorized_address
    )


def test_add_personal_authorized_event(currency_network_adapter, accounts):
    target = accounts[3]
    sender = accounts[4]
    currency_network_adapter.add_authorized_address(target=target, sender=sender)

    events = currency_network_adapter.events("AuthorizedAddressAdd")
    assert len(events) == 1
    assert events[0]["args"]["authorized"] == target
    assert events[0]["args"]["allower"] == sender


def test_remove_personal_authorized_event(currency_network_adapter, accounts):
    target = accounts[3]
    sender = accounts[4]
    currency_network_adapter.add_authorized_address(target=target, sender=sender)
    currency_network_adapter.remove_authorized_address(target=target, sender=sender)

    events = currency_network_adapter.events("AuthorizedAddressRemove")
    assert len(events) == 1
    assert events[0]["args"]["authorized"] == target
    assert events[0]["args"]["allower"] == sender
