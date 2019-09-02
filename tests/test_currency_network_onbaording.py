import pytest

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
    "account_management_enabled": True,
    "expiration_time": EXPIRATION_TIME,
}

ADDRESS_0 = "0x0000000000000000000000000000000000000000"
NO_ONBOARDER = "0x0000000000000000000000000000000000000001"


@pytest.fixture(scope="session")
def currency_network_contract(web3):
    return deploy_network(web3, **NETWORK_SETTING)


def open_trustline(network, a, b):
    network.functions.updateTrustlineDefaultInterests(b, 1, 1, False).transact(
        {"from": a}
    )
    network.functions.updateTrustlineDefaultInterests(a, 1, 1, False).transact(
        {"from": b}
    )


def test_no_onboarder(currency_network_contract, accounts):
    open_trustline(currency_network_contract, accounts[1], accounts[2])

    assert (
        currency_network_contract.functions.onBoarder(accounts[1]).call()
        == NO_ONBOARDER
    )
    assert (
        currency_network_contract.functions.onBoarder(accounts[2]).call()
        == NO_ONBOARDER
    )


def test_onboarder_simple_trustline(currency_network_contract, accounts):
    open_trustline(currency_network_contract, accounts[1], accounts[2])
    open_trustline(currency_network_contract, accounts[2], accounts[3])

    assert (
        currency_network_contract.functions.onBoarder(accounts[3]).call() == accounts[2]
    )


def test_cannot_change_no_onbaorder(currency_network_contract, accounts):
    open_trustline(currency_network_contract, accounts[1], accounts[2])
    assert (
        currency_network_contract.functions.onBoarder(accounts[2]).call()
        == NO_ONBOARDER
    )

    open_trustline(currency_network_contract, accounts[2], accounts[3])
    assert (
        currency_network_contract.functions.onBoarder(accounts[2]).call()
        == NO_ONBOARDER
    )


def test_cannot_change_onbaorder(currency_network_contract, accounts):
    open_trustline(currency_network_contract, accounts[1], accounts[2])
    open_trustline(currency_network_contract, accounts[2], accounts[3])
    assert (
        currency_network_contract.functions.onBoarder(accounts[3]).call() == accounts[2]
    )

    open_trustline(currency_network_contract, accounts[3], accounts[4])
    assert (
        currency_network_contract.functions.onBoarder(accounts[3]).call() == accounts[2]
    )


def test_set_account_onboards(currency_network_contract, accounts):
    currency_network_contract.functions.setAccountDefaultInterests(
        accounts[1], accounts[2], 1, 1, False, 1, 1, 1, 1
    ).transact()

    owner = accounts[0]
    assert currency_network_contract.functions.onBoarder(accounts[1]).call() == owner
    assert currency_network_contract.functions.onBoarder(accounts[2]).call() == owner


def test_onboarding_event_no_onboarder(currency_network_contract, web3, accounts):
    intial_block = web3.eth.blockNumber

    open_trustline(currency_network_contract, accounts[1], accounts[2])

    all_events = currency_network_contract.events.OnBoarding.createFilter(
        fromBlock=intial_block
    ).get_all_entries()
    event_onboarding_1 = currency_network_contract.events.OnBoarding.createFilter(
        fromBlock=intial_block, argument_filters={"_onBoardee": accounts[1]}
    ).get_all_entries()

    assert len(all_events) == 2
    assert event_onboarding_1[0]["args"]["_onBoarder"] == NO_ONBOARDER


def test_onboarding_event_with_onboarder(currency_network_contract, web3, accounts):
    intial_block = web3.eth.blockNumber

    open_trustline(currency_network_contract, accounts[1], accounts[2])
    open_trustline(currency_network_contract, accounts[2], accounts[3])

    all_events = currency_network_contract.events.OnBoarding.createFilter(
        fromBlock=intial_block
    ).get_all_entries()
    event_onboarding_3 = currency_network_contract.events.OnBoarding.createFilter(
        fromBlock=intial_block, argument_filters={"_onBoardee": accounts[3]}
    ).get_all_entries()

    assert len(all_events) == 3
    assert event_onboarding_3[0]["args"]["_onBoarder"] == accounts[2]
