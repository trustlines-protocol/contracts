#! pytest

import pytest

import eth_tester.exceptions
from tldeploy.core import deploy_network

from .conftest import EXTRA_DATA, EXPIRATION_TIME, CurrencyNetworkAdapter


trustlines = [
    (0, 1, 100, 150),
    (1, 2, 200, 250),
    (2, 3, 300, 350),
    (3, 4, 400, 450),
    (0, 4, 500, 550),
]  # (A, B, clAB, clBA)


@pytest.fixture(scope="session")
def currency_network_contract_with_trustlines(web3, accounts):
    contract = deploy_network(
        web3,
        currency_network_contract_name="TestCurrencyNetwork",
        name="TestCoin",
        symbol="T",
        decimals=6,
        fee_divisor=100,
        expiration_time=EXPIRATION_TIME,
    )
    for (A, B, clAB, clBA) in trustlines:
        CurrencyNetworkAdapter(contract).set_account(
            accounts[A], accounts[B], creditline_given=clAB, creditline_received=clBA
        )
    return contract


def test_transfer_0_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transfer(
        100, 0, [accounts[0], accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -100


def test_transfer_0_mediators_fail_not_enough_credit(
    currency_network_contract_with_trustlines, accounts
):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transfer(
            151, 0, [accounts[0], accounts[1]], EXTRA_DATA
        ).transact({"from": accounts[0]})


def test_transfer_1_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transfer(
        50, 1, [accounts[0], accounts[1], accounts[2]], EXTRA_DATA
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -50 - 1
    assert contract.functions.balance(accounts[2], accounts[1]).call() == 50


def test_transfer_1_mediators_not_enough_credit(
    currency_network_contract_with_trustlines, accounts
):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transfer(
            151 - 2, 2, [accounts[0], accounts[1], accounts[2]], EXTRA_DATA
        ).transact({"from": accounts[0]})


def test_transfer_3_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transfer(
        100,
        6,
        [accounts[0], accounts[1], accounts[2], accounts[3], accounts[4]],
        EXTRA_DATA,
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -100 - 6
    assert contract.functions.balance(accounts[1], accounts[2]).call() == -100 - 4
    assert contract.functions.balance(accounts[2], accounts[3]).call() == -100 - 2
    assert contract.functions.balance(accounts[4], accounts[3]).call() == 100


def test_rounding_fee(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    # test that fee is really 1%
    contract.functions.transfer(
        99, 1, [accounts[0], accounts[1], accounts[2]], EXTRA_DATA
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -99 - 1


def test_max_fee(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transfer(
            110, 1, [accounts[0], accounts[1], accounts[2]], EXTRA_DATA
        ).transact({"from": accounts[0]})


def test_send_back_with_fees(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 0
    contract.functions.transfer(
        120, 2, [accounts[0], accounts[1], accounts[2]], EXTRA_DATA
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[2], accounts[1]).call() == 120
    contract.functions.transfer(
        120, 0, [accounts[2], accounts[1], accounts[0]], EXTRA_DATA
    ).transact({"from": accounts[2]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 0 - 2


def test_send_more_with_fees(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 0
    contract.functions.transfer(
        120, 2, [accounts[0], accounts[1], accounts[2]], EXTRA_DATA
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[2], accounts[1]).call() == 120
    contract.functions.transfer(
        200, 1, [accounts[2], accounts[1], accounts[0]], EXTRA_DATA
    ).transact({"from": accounts[2]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 80 - 2
    assert contract.functions.balance(accounts[2], accounts[1]).call() == -80 - 1
