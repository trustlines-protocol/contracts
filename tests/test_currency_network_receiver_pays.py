#! pytest

import pytest
from tldeploy.core import deploy_network
import eth_tester.exceptions

from .conftest import EXTRA_DATA, EXPIRATION_TIME

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
        name="TestCoin",
        symbol="T",
        decimals=6,
        fee_divisor=100,
        currency_network_contract_name="TestCurrencyNetwork",
        expiration_time=EXPIRATION_TIME,
    )
    for (A, B, clAB, clBA) in trustlines:
        contract.functions.setAccount(
            accounts[A], accounts[B], clAB, clBA, 0, 0, False, 0, 0
        ).transact()
    return contract


@pytest.fixture(scope="session")
def currency_network_contract_with_high_trustlines(web3, accounts):
    contract = deploy_network(
        web3,
        name="TestCoin",
        symbol="T",
        decimals=6,
        fee_divisor=100,
        currency_network_contract_name="TestCurrencyNetwork",
        expiration_time=EXPIRATION_TIME,
    )
    creditline = 1000000
    contract.functions.setAccount(
        accounts[0], accounts[1], creditline, creditline, 0, 0, False, 0, 0
    ).transact()
    contract.functions.setAccount(
        accounts[1], accounts[2], creditline, creditline, 0, 0, False, 0, 0
    ).transact()
    contract.functions.setAccount(
        accounts[2], accounts[3], creditline, creditline, 0, 0, False, 0, 0
    ).transact()

    contract.functions.setAccount(
        accounts[0], accounts[2], creditline, creditline, 0, 0, False, 0, 0
    ).transact()
    contract.functions.setAccount(
        accounts[2], accounts[4], creditline, creditline, 0, 0, False, 0, 0
    ).transact()
    contract.functions.setAccount(
        accounts[4], accounts[3], creditline, creditline, 0, 0, False, 0, 0
    ).transact()

    return contract


def test_transfer_0_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transferReceiverPays(
        accounts[1], 100, 0, [accounts[1]], EXTRA_DATA
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -100


def test_transfer_0_mediators_fail_not_enough_credit(
    currency_network_contract_with_trustlines, accounts
):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transferReceiverPays(
            accounts[1], 151, 0, [accounts[1]], EXTRA_DATA
        ).transact({"from": accounts[0]})


def test_transfer_1_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transferReceiverPays(
        accounts[2], 50, 1, [accounts[1], accounts[2]], EXTRA_DATA
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -50
    assert contract.functions.balance(accounts[2], accounts[1]).call() == 50 - 1


def test_transfer_1_mediator_enough_credit_because_of_fee(
    currency_network_contract_with_trustlines, accounts
):
    contract = currency_network_contract_with_trustlines
    contract.functions.transferReceiverPays(
        accounts[0], 100 + 2, 2, [accounts[1], accounts[0]], EXTRA_DATA
    ).transact({"from": accounts[2]})


def test_transfer_3_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transferReceiverPays(
        accounts[4],
        100,
        3,
        [accounts[1], accounts[2], accounts[3], accounts[4]],
        EXTRA_DATA,
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -100
    assert contract.functions.balance(accounts[1], accounts[2]).call() == -100 + 1
    assert contract.functions.balance(accounts[2], accounts[3]).call() == -100 + 2
    assert contract.functions.balance(accounts[4], accounts[3]).call() == 100 - 3


def test_rounding_fee(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transferReceiverPays(
        accounts[2], 100, 1, [accounts[1], accounts[2]], EXTRA_DATA
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[2], accounts[1]).call() == 100 - 1


def test_max_fee(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transferReceiverPays(
            accounts[2], 110, 1, [accounts[1], accounts[2]], EXTRA_DATA
        ).transact({"from": accounts[0]})


def test_max_fee_3_mediators(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transferReceiverPays(
            accounts[4],
            50,
            2,
            [accounts[1], accounts[2], accounts[3], accounts[4]],
            EXTRA_DATA,
        ).transact({"from": accounts[0]})


def test_send_back_with_fees(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 0
    contract.functions.transferReceiverPays(
        accounts[2], 120, 2, [accounts[1], accounts[2]], EXTRA_DATA
    ).transact({"from": accounts[0]})
    contract.functions.transferReceiverPays(
        accounts[2], 20, 1, [accounts[2]], EXTRA_DATA
    ).transact({"from": accounts[1]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -120
    assert contract.functions.balance(accounts[2], accounts[1]).call() == 20 + 118
    contract.functions.transferReceiverPays(
        accounts[0], 120, 0, [accounts[1], accounts[0]], EXTRA_DATA
    ).transact({"from": accounts[2]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 0
    assert contract.functions.balance(accounts[2], accounts[1]).call() == 20 - 2


def test_send_more_with_fees(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 0
    contract.functions.transferReceiverPays(
        accounts[2], 120, 2, [accounts[1], accounts[2]], EXTRA_DATA
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == -120
    contract.functions.transferReceiverPays(
        accounts[0], 200, 1, [accounts[1], accounts[0]], EXTRA_DATA
    ).transact({"from": accounts[2]})
    assert contract.functions.balance(accounts[0], accounts[1]).call() == 80 - 1
    assert contract.functions.balance(accounts[2], accounts[1]).call() == -80 - 2


def test_transfer_1_received(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    contract.functions.transferReceiverPays(
        accounts[4],
        4,
        3,
        [accounts[1], accounts[2], accounts[3], accounts[4]],
        EXTRA_DATA,
    ).transact({"from": accounts[0]})
    assert contract.functions.balance(accounts[4], accounts[3]).call() == 1


def test_transfer_0_received(currency_network_contract_with_trustlines, accounts):
    contract = currency_network_contract_with_trustlines
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        contract.functions.transferReceiverPays(
            accounts[4],
            3,
            3,
            [accounts[1], accounts[2], accounts[3], accounts[4]],
            EXTRA_DATA,
        ).transact({"from": accounts[0]})


@pytest.mark.parametrize(
    "value", [4, 100, 101, 102, 1000, 9999, 10000, 10001, 50000, 50506, 123456]
)
def test_fees_are_the_same(
    currency_network_contract_with_high_trustlines, accounts, value
):
    """Test that the fees are the same, no matter if the sender or the receiver pays the fees
    For that we check that if someone sends a transfer where the receiver pays, so `value` is sent but a smaller
    amount `received` is received, it will result in the same value sent if sender pays is chosen and `received`
    is used as value for this transfer.
    Because the fee function is not injective we allow for a difference of 1
    """
    contract = currency_network_contract_with_high_trustlines
    contract.functions.transferReceiverPays(
        accounts[3], value, 10000, [accounts[1], accounts[2], accounts[3]], EXTRA_DATA
    ).transact({"from": accounts[0]})
    return_value = contract.functions.balance(accounts[3], accounts[2]).call()
    contract.functions.transfer(
        accounts[3],
        return_value,
        10000,
        [accounts[2], accounts[4], accounts[3]],
        EXTRA_DATA,
    ).transact({"from": accounts[0]})
    balance_sender = contract.functions.balance(accounts[0], accounts[2]).call()
    # value can be one wrong because the fee function is not injective
    assert balance_sender == pytest.approx(-value, abs=1)
