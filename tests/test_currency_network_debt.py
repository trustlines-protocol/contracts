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

max_int72 = 2 ** 71 - 1
min_int72 = -(max_int72 + 1)

NETWORK_SETTING = {
    "name": "TestCoin",
    "symbol": "T",
    "decimals": 6,
    "fee_divisor": 100,
    "default_interest_rate": 0,
    "custom_interests": False,
    "currency_network_contract_name": "TestCurrencyNetwork",
    "expiration_time": EXPIRATION_TIME,
}


@pytest.fixture(scope="session")
def currency_network_contract(web3):
    return deploy_network(web3, **NETWORK_SETTING)


@pytest.fixture(scope="session")
def currency_network_contract_with_trustlines(web3, accounts):
    contract = deploy_network(web3, **NETWORK_SETTING)
    for (A, B, clAB, clBA) in trustlines:
        contract.functions.setAccount(
            accounts[A], accounts[B], clAB, clBA, 0, 0, False, 0, 0, 0, 0
        ).transact()
    return contract


@pytest.fixture(scope="session")
def debtor(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def creditor(accounts):
    return accounts[3]


@pytest.fixture(scope="session")
def debt_value():
    return 51


@pytest.fixture(scope="session")
def currency_network_contract_with_trustlines_and_debt(
    currency_network_contract_with_trustlines, debtor, creditor, debt_value
):
    currency_network_contract_with_trustlines.functions.increaseDebt(
        creditor, debt_value
    ).transact({"from": debtor})
    return currency_network_contract_with_trustlines


@pytest.mark.parametrize("creditor, debtor", [(0, 1), (1, 0)])
def test_increasing_debt(currency_network_contract, accounts, creditor, debtor):
    debt_value = 123

    currency_network_contract.functions.increaseDebt(
        accounts[creditor], debt_value
    ).transact({"from": accounts[debtor]})

    debt = currency_network_contract.functions.getDebt(
        accounts[debtor], accounts[creditor]
    ).call()
    reverse_debt = currency_network_contract.functions.getDebt(
        accounts[creditor], accounts[debtor]
    ).call()

    assert debt == debt_value
    assert reverse_debt == -debt_value


@pytest.mark.parametrize("creditor, debtor", [(0, 1), (1, 0)])
def test_increasing_debt_event(
    currency_network_contract, accounts, creditor, debtor, web3
):
    debt_value = 123

    initial_block = web3.eth.blockNumber

    currency_network_contract.functions.increaseDebt(
        accounts[creditor], debt_value
    ).transact({"from": accounts[debtor]})

    event = currency_network_contract.events.DebtUpdate.createFilter(
        fromBlock=initial_block
    ).get_all_entries()[0]["args"]

    assert event["_debtor"] == accounts[debtor]
    assert event["_creditor"] == accounts[creditor]
    assert event["_newDebt"] == debt_value


def test_debit_transfer(
    currency_network_contract_with_trustlines_and_debt,
    accounts,
    creditor,
    debtor,
    debt_value,
):
    network = currency_network_contract_with_trustlines_and_debt

    path = [accounts[1], accounts[2], creditor]
    transfer_fees = 2

    network.functions.debitTransfer(
        debtor, creditor, debt_value, transfer_fees, path, EXTRA_DATA
    ).transact({"from": creditor})

    assert network.functions.getDebt(debtor, creditor).call() == 0
    assert network.functions.balance(debtor, accounts[1]).call() == -debt_value
    assert (
        network.functions.balance(creditor, accounts[2]).call()
        == debt_value - transfer_fees
    )


def test_debit_transfer_over_value(
    currency_network_contract_with_trustlines_and_debt,
    accounts,
    creditor,
    debtor,
    debt_value,
):
    network = currency_network_contract_with_trustlines_and_debt

    path = [accounts[1], accounts[2], creditor]
    transfer_fees = 2

    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        network.functions.debitTransfer(
            debtor, creditor, debt_value + 1, transfer_fees, path, EXTRA_DATA
        ).transact({"from": creditor})


def test_debit_transfer_under_value(
    currency_network_contract_with_trustlines_and_debt,
    accounts,
    creditor,
    debtor,
    debt_value,
):
    network = currency_network_contract_with_trustlines_and_debt

    path = [accounts[1], accounts[2], creditor]
    transfer_value = debt_value // 2
    transfer_fees = 2

    network.functions.debitTransfer(
        debtor, creditor, transfer_value, transfer_fees, path, EXTRA_DATA
    ).transact({"from": creditor})

    assert (
        network.functions.getDebt(debtor, creditor).call()
        == debt_value - transfer_value
    )
    assert network.functions.balance(debtor, accounts[1]).call() == -transfer_value
    assert (
        network.functions.balance(creditor, accounts[2]).call()
        == transfer_value - transfer_fees
    )


def test_debit_transfer_revert(
    currency_network_contract_with_trustlines_and_debt,
    accounts,
    creditor,
    debtor,
    debt_value,
):
    network = currency_network_contract_with_trustlines_and_debt

    path = [accounts[1], accounts[1], creditor]
    transfer_value = debt_value // 2
    invalid_transfer_fees = 0

    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        network.functions.debitTransfer(
            debtor, creditor, transfer_value, invalid_transfer_fees, path, EXTRA_DATA
        ).transact({"from": creditor})


def test_debit_transfer_events(
    currency_network_contract_with_trustlines_and_debt,
    accounts,
    creditor,
    debtor,
    debt_value,
):
    network = currency_network_contract_with_trustlines_and_debt
    debt_event_filter = network.events.DebtUpdate.createFilter(fromBlock="latest")
    transfer_event_filter = network.events.Transfer.createFilter(fromBlock="latest")

    path = [accounts[1], accounts[2], creditor]
    transfer_fees = 2

    network.functions.debitTransfer(
        debtor, creditor, debt_value, transfer_fees, path, EXTRA_DATA
    ).transact({"from": creditor})

    debt_event = debt_event_filter.get_new_entries()[0]["args"]
    assert debt_event["_debtor"] == debtor
    assert debt_event["_creditor"] == creditor
    assert debt_event["_newDebt"] == 0

    transfer_event = transfer_event_filter.get_new_entries()[0]["args"]
    assert transfer_event["_from"] == debtor
    assert transfer_event["_to"] == creditor
    assert transfer_event["_value"] == debt_value


@pytest.mark.parametrize(
    "a, b",
    [
        (0, 1),
        (1, 0),
        (max_int72, 0),
        (max_int72, -1),
        (max_int72, min_int72),
        (min_int72, 0),
        (min_int72, 1),
    ],
)
def test_safe_sum_no_error(currency_network_contract, a, b):
    assert currency_network_contract.functions.testSafeSum(a, b).call() == a + b


@pytest.mark.parametrize(
    "a, b",
    [(max_int72, max_int72), (max_int72, 1), (min_int72, -1), (min_int72, min_int72)],
)
def test_safe_sum_raises_error(currency_network_contract, a, b):
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        currency_network_contract.functions.testSafeSum(a, b).call()
