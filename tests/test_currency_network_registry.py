#! pytest
import pytest
import eth_tester.exceptions

from tldeploy.core import deploy_network
from .conftest import EXPIRATION_TIME


NETWORK_SETTING = {
    "name": "TestCoin",
    "symbol": "T",
    "decimals": 6,
    "fee_divisor": 0,
    "default_interest_rate": 0,
    "custom_interests": False,
    "currency_network_contract_name": "TestCurrencyNetwork",
    "set_account_enabled": True,
    "expiration_time": EXPIRATION_TIME,
}


@pytest.fixture
def currency_network_contract(web3):
    return deploy_network(web3, **NETWORK_SETTING)


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


def test_add_network_once(
    initialized_currency_network_registry_contract, currency_network_contract
):
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        initialized_currency_network_registry_contract.functions.addCurrencyNetwork(
            currency_network_contract.address
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
    assert events[0]["args"]["_author"] == default_account
    assert events[0]["args"]["_name"] == NETWORK_SETTING["name"]
    assert events[0]["args"]["_symbol"] == NETWORK_SETTING["symbol"]
    assert events[0]["args"]["_decimals"] == NETWORK_SETTING["decimals"]
