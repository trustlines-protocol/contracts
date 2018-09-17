#! pytest

import pytest
from tldeploy.core import deploy_network
import eth_tester.exceptions


trustlines = [(0, 1, 100, 150),
              (1, 2, 200, 250),
              (2, 3, 300, 350),
              (3, 4, 400, 450),
              (0, 4, 500, 550)
              ]  # (A, B, clAB, clBA)


@pytest.fixture()
def currency_network_contract(web3):
    return deploy_network(web3, name="TestCoin", symbol="T", decimals=6, fee_divisor=100)


@pytest.fixture()
def currency_network_contract_with_trustlines(currency_network_contract, accounts):
    contract = currency_network_contract
    for (A, B, clAB, clBA) in trustlines:
        contract.functions.setAccount(accounts[A], accounts[B], clAB, clBA, 0, 0, 0, 0, 0, 0).transact()
    return contract


def test_transfer_0_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transfer(accounts[1], 100, 2, [accounts[1]]).transact({'from': accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -100 - 2


def test_transfer_0_mediators_fail_not_enough_credit(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transfer(accounts[1], 151 - 2, 2, [accounts[1]]).transact({'from': accounts[0]})


def test_transfer_1_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transfer(accounts[2], 50, 2, [accounts[1], accounts[2]]).transact({'from': accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -50 - 2
    assert contract.functions.balance(accounts[2], accounts[1]).call() == 50 + 1


def test_transfer_1_mediators_not_enough_credit(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transfer(
            accounts[2],
            151 - 2,
            2,
            [accounts[1], accounts[2]]).transact({'from': accounts[0]})


def test_transfer_3_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transfer(accounts[4], 100, 8, [accounts[1],
                                                      accounts[2],
                                                      accounts[3],
                                                      accounts[4]]).transact({'from': accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -100 - 8
    assert contract.functions.balance(accounts[1], accounts[2]).call() == -100 - 6
    assert contract.functions.balance(accounts[2], accounts[3]).call() == -100 - 4
    assert contract.functions.balance(accounts[4], accounts[3]).call() == 100 + 2


def test_spendable(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.functions.spendableTo(A, B).call() == 150
    assert contract.functions.spendableTo(B, A).call() == 100
    contract.functions.transfer(B, 40, 1, [B]).transact({"from": A})
    assert contract.functions.spendableTo(A, B).call() == 110 - 1
    assert contract.functions.spendableTo(B, A).call() == 140 + 1


def test_max_fee(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transfer(accounts[1], 100, 1, [accounts[1]]).transact({'from': accounts[0]})


def test_send_back_with_fees(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 0
    contract.functions.transfer(accounts[1], 120, 2, [accounts[1]]).transact({'from': accounts[0]})
    assert contract.functions.balance(accounts[1], accounts[0]).call() == 120 + 2
    contract.functions.transfer(accounts[0], 120, 0, [accounts[0]]).transact({'from': accounts[1]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 0 - 2


def test_send_more_with_fees(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 0
    contract.functions.transfer(accounts[1], 120, 2, [accounts[1]]).transact({'from': accounts[0]})
    assert contract.functions.balance(accounts[1], accounts[0]).call() == 120 + 2
    contract.functions.transfer(accounts[0], 200, 1, [accounts[0]]).transact({'from': accounts[1]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 80 - 2 + 1
