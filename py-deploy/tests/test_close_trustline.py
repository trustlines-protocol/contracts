#! pytest

import pytest
from tldeploy.core import deploy_network


@pytest.fixture()
def currency_network_contract(web3):
    return deploy_network(
        web3, name="TestCoin", symbol="T", decimals=6, fee_divisor=100
    )


@pytest.fixture
def currency_network_contract_with_trustlines(currency_network_contract, accounts):
    for a in accounts:
        for b in accounts:
            if a is b:
                continue
            currency_network_contract.functions.setAccount(
                a, b, 1000000, 1000000, 0, 0, 0, 0, 0, 0
            ).transact()

    currency_network_contract.functions.transfer(
        accounts[1], 10000, 102, [accounts[1]]
    ).transact({"from": accounts[0]})
    return currency_network_contract


def ensure_trustline_closed(contract, address1, address2):
    assert contract.functions.getAccount(address1, address2).call() == [
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    ]

    assert address2 not in contract.functions.getFriends(address1).call()
    assert address1 not in contract.functions.getFriends(address2).call()


def test_close_trustline_negative_balance(
    currency_network_contract_with_trustlines, accounts
):
    contract = currency_network_contract_with_trustlines

    def get_balance():
        return contract.functions.balance(accounts[0], accounts[1]).call()

    assert get_balance() < 0

    contract.functions.closeTrustlineByTriangularTransfer(
        accounts[1], 1000, [accounts[2], accounts[3], accounts[1], accounts[0]]
    ).transact({"from": accounts[0]})

    assert get_balance() == 0
    ensure_trustline_closed(contract, accounts[0], accounts[1])


def test_close_trustline_positive_balance(
    currency_network_contract_with_trustlines, accounts
):
    contract = currency_network_contract_with_trustlines

    def get_balance():
        return contract.functions.balance(accounts[1], accounts[0]).call()

    assert get_balance() > 0

    contract.functions.closeTrustlineByTriangularTransfer(
        accounts[0], 1000, [accounts[0], accounts[2], accounts[3], accounts[1]]
    ).transact({"from": accounts[1]})

    assert get_balance() == 0
    ensure_trustline_closed(contract, accounts[0], accounts[1])
