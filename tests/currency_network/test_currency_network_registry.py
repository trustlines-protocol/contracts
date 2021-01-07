#! pytest
import pytest
import eth_tester.exceptions

from tests.currency_network.conftest import NETWORK_SETTING


@pytest.fixture
def currency_network_registry_contract(deploy_contract):
    return deploy_contract("CurrencyNetworkRegistry")


@pytest.fixture
def initialized_currency_network_registry_contract(
    currency_network_registry_contract, currency_network_contract
):
    currency_network_registry_contract.functions.addCurrencyNetwork(
        currency_network_contract.address
    ).transact()
    return currency_network_registry_contract


def test_add_network(currency_network_registry_contract, currency_network_contract):
    assert (
        currency_network_registry_contract.functions.getCurrencyNetworkCount().call()
        == 0
    )
    currency_network_registry_contract.functions.addCurrencyNetwork(
        currency_network_contract.address
    ).transact()
    assert (
        currency_network_registry_contract.functions.getCurrencyNetworkCount().call()
        == 1
    )


def test_add_network_multiple(
    initialized_currency_network_registry_contract, currency_network_contract, accounts
):
    initialized_currency_network_registry_contract.functions.addCurrencyNetwork(
        currency_network_contract.address
    ).transact({"from": accounts[1]})

    # Sadly there is no cost-efficient way to check if the contract address has already been registered with this
    # address, so it's possible to add the network twice. Which we also check here is possible.
    initialized_currency_network_registry_contract.functions.addCurrencyNetwork(
        currency_network_contract.address
    ).transact({"from": accounts[1]})

    # The number of actual networks should remain 1 as there is only one address
    assert (
        initialized_currency_network_registry_contract.functions.getCurrencyNetworkCount().call()
        == 1
    )

    # The first account registered the network once
    assert (
        len(
            initialized_currency_network_registry_contract.functions.getCurrencyNetworksRegisteredBy(
                accounts[0]
            ).call()
        )
        == 1
    )

    # The second account registered the network twice
    assert (
        len(
            initialized_currency_network_registry_contract.functions.getCurrencyNetworksRegisteredBy(
                accounts[1]
            ).call()
        )
        == 2
    )


def test_add_network_twice_does_not_change_metadata(
    initialized_currency_network_registry_contract, currency_network_contract, accounts
):
    """Adding the same network again does not change the initial information.

    Each new registration emits an event with the new registrar, but the
    original registrar from the first call does change.
    """

    currency_network_metadata = initialized_currency_network_registry_contract.functions.getCurrencyNetworkMetadata(
        currency_network_contract.address
    ).call()

    initialized_currency_network_registry_contract.functions.addCurrencyNetwork(
        currency_network_contract.address
    ).transact({"from": accounts[1]})

    initialized_currency_network_registry_contract.functions.getCurrencyNetworkMetadata(
        currency_network_contract.address
    ).call()
    assert (
        initialized_currency_network_registry_contract.functions.getCurrencyNetworkMetadata(
            currency_network_contract.address
        ).call()[
            0
        ]
        == currency_network_metadata[0]
    )


def test_add_network_multiple_events(
    currency_network_registry_contract, currency_network_contract, accounts
):
    """Adding the same network with multiple accounts.

    Each call emits a new event with the corresponding account as
    registrar.
    """

    currency_added_event_filter = currency_network_registry_contract.events.CurrencyNetworkAdded.createFilter(
        fromBlock=0
    )
    currency_network_registry_contract.functions.addCurrencyNetwork(
        currency_network_contract.address
    ).transact({"from": accounts[0]})

    currency_added_event_list = currency_added_event_filter.get_new_entries()
    assert len(currency_added_event_list) == 1
    assert currency_added_event_list[0].args._registeredBy == accounts[0]

    currency_network_registry_contract.functions.addCurrencyNetwork(
        currency_network_contract.address
    ).transact({"from": accounts[1]})

    currency_added_event_list = currency_added_event_filter.get_new_entries()
    assert len(currency_added_event_list) == 1
    assert currency_added_event_list[0].args._registeredBy == accounts[1]


def test_add_invalid_network(initialized_currency_network_registry_contract, accounts):
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        initialized_currency_network_registry_contract.functions.addCurrencyNetwork(
            accounts[2]
        ).transact()


def test_get_address(
    initialized_currency_network_registry_contract, currency_network_contract
):
    assert (
        initialized_currency_network_registry_contract.functions.getCurrencyNetworkAddress(
            0
        ).call()
        == currency_network_contract.address
    )


def test_get_metadata(
    initialized_currency_network_registry_contract,
    currency_network_contract,
    default_account,
):
    metadata = initialized_currency_network_registry_contract.functions.getCurrencyNetworkMetadata(
        currency_network_contract.address
    ).call()
    assert metadata[0] == default_account
    assert metadata[1] == NETWORK_SETTING["name"]
    assert metadata[2] == NETWORK_SETTING["symbol"]
    assert metadata[3] == NETWORK_SETTING["decimals"]


def test_no_events(currency_network_registry_contract):
    events = currency_network_registry_contract.events.CurrencyNetworkAdded.createFilter(
        fromBlock=0
    ).get_all_entries()
    assert len(events) == 0


def test_add_event(initialized_currency_network_registry_contract, default_account):
    events = initialized_currency_network_registry_contract.events.CurrencyNetworkAdded.createFilter(
        fromBlock=0
    ).get_all_entries()
    assert len(events) == 1
    assert events[0]["event"] == "CurrencyNetworkAdded"
    assert events[0]["args"]["_registeredBy"] == default_account
    assert events[0]["args"]["_name"] == NETWORK_SETTING["name"]
    assert events[0]["args"]["_symbol"] == NETWORK_SETTING["symbol"]
    assert events[0]["args"]["_decimals"] == NETWORK_SETTING["decimals"]
