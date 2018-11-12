#! pytest

import time
import pytest
from tldeploy.core import deploy_network


SECONDS_PER_YEAR = 60 * 60 * 24 * 365


@pytest.fixture()
def currency_network_contract(web3):
    return deploy_network(
        web3,
        name="TestCoin",
        symbol="T",
        decimals=6,
        fee_divisor=100,
        default_interest_rate=0,
        custom_interests=True,
        prevent_mediator_interests=False,
    )


@pytest.fixture(params=[0, 100, 2000])  # 0% , 1%, 20%
def interest_rate(request):
    return request.param


@pytest.fixture
def currency_network_contract_with_trustlines(
    ethereum_tester_session, currency_network_contract, accounts, interest_rate
):
    current_time = int(time.time())
    ethereum_tester_session.time_travel(current_time + 10)

    for a in accounts:
        for b in accounts:
            if a is b:
                continue
            currency_network_contract.functions.setAccount(
                a,
                b,
                1000000,  # creditline given
                1000000,  # creditline received
                interest_rate,  # interest rate given
                interest_rate,  # interest rate received
                0,  # fees outstanding a
                0,  # fees outstanding b
                current_time,
                0,  # balance
            ).transact()

    currency_network_contract.functions.transfer(
        accounts[1], 10000, 102, [accounts[1]]
    ).transact({"from": accounts[0]})

    ethereum_tester_session.time_travel(current_time + SECONDS_PER_YEAR)

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
