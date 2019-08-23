import pytest

from tldeploy.core import deploy_network
import eth_tester.exceptions

from .conftest import EXPIRATION_TIME


NETWORK_SETTING = {
    "name": "TestCoin",
    "symbol": "T",
    "decimals": 6,
    "fee_divisor": 0,
    "default_interest_rate": 0,
    "custom_interests": False,
    "currency_network_contract_name": "TestCurrencyNetwork",
    "expiration_time": EXPIRATION_TIME,
}


trustlines = [
    (0, 1, 100, 150),
    (1, 2, 200, 250),
    (2, 0, 300, 300),
    (2, 3, 300, 350),
    (3, 4, 400, 450),
    (0, 4, 500, 550),
]  # (A, B, clAB, clBA)


@pytest.fixture(scope="session")
def currency_network_contract(web3):
    return deploy_network(web3, **NETWORK_SETTING)


@pytest.fixture(scope="session")
def currency_network_contract_with_trustlines(web3, accounts, chain):
    contract = deploy_network(web3, **NETWORK_SETTING)
    for (A, B, clAB, clBA) in trustlines:
        contract.functions.setAccount(
            accounts[A], accounts[B], clAB, clBA, 0, 0, 0, 0, 0, 0
        ).transact()

    return contract


@pytest.fixture()
def frozen_currency_network_contract_with_trustlines(
    currency_network_contract_with_trustlines, chain
):
    chain.time_travel(EXPIRATION_TIME)
    chain.mine_block()
    currency_network_contract_with_trustlines.functions.freezeNetwork().transact()
    return currency_network_contract_with_trustlines


@pytest.fixture(scope="session")
def frozen_functions_and_args(accounts):
    """
    returns a list of functions that should fail when the network is frozen and their arguments
    the functions are expected to be called from accounts[0]
    """
    return [
        ["transfer", (accounts[1], 1, 2, [accounts[1]], b"")],
        ["transferReceiverPays", (accounts[1], 1, 2, [accounts[1]], b"")],
        ["transferFrom", (accounts[0], accounts[1], 1, 2, [accounts[1]], b"")],
        ["updateTrustline", (accounts[1], 101, 101, 101, 101)],
        ["updateCreditlimits", (accounts[1], 101, 101)],
        ["updateTrustlineDefaultInterests", (accounts[1], 101, 101)],
        ["closeTrustline", [accounts[1]]],
        [
            "closeTrustlineByTriangularTransfer",
            (accounts[1], 100, [accounts[1], accounts[2]]),
        ],
    ]


def test_freeze_too_soon(currency_network_contract):
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        currency_network_contract.functions.freezeNetwork().transact()


def test_freeze(currency_network_contract, chain):
    assert currency_network_contract.functions.isNetworkFrozen().call() is False

    chain.time_travel(EXPIRATION_TIME)
    chain.mine_block()

    currency_network_contract.functions.freezeNetwork().transact()

    assert currency_network_contract.functions.isNetworkFrozen().call() is True


def test_trustline_frozen_if_network_frozen(
    frozen_currency_network_contract_with_trustlines, chain, accounts
):
    assert (
        frozen_currency_network_contract_with_trustlines.functions.isTrustlineFrozen(
            accounts[0], accounts[1]
        ).call()
        is True
    )
    assert (
        frozen_currency_network_contract_with_trustlines.functions.getAccount(
            accounts[0], accounts[1]
        ).call()[4]
        is True
    )


def test_interaction_fails_if_network_frozen(
    frozen_currency_network_contract_with_trustlines,
    frozen_functions_and_args,
    accounts,
):
    network = frozen_currency_network_contract_with_trustlines

    # we need to authorize this address for testing transferFrom()
    network.functions.addAuthorizedAddress(accounts[0]).transact()

    for (function_name, arguments) in frozen_functions_and_args:
        with pytest.raises(eth_tester.exceptions.TransactionFailed):
            getattr(network.functions, function_name)(*arguments).transact(
                {"from": accounts[0]}
            )
