#! pytest

import pytest

from tldeploy.core import deploy_network
import eth_tester.exceptions

from tests.conftest import EXTRA_DATA, EXPIRATION_TIME, CurrencyNetworkAdapter

trustlines = [
    (0, 1, 100, 150),
    (1, 2, 200, 250),
    (2, 3, 300, 350),
    (3, 4, 400, 450),
    (0, 4, 500, 550),
]  # (A, B, clAB, clBA)

max_int256 = 2 ** 255 - 1
min_int256 = -(max_int256 + 1)

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
        CurrencyNetworkAdapter(contract).set_account(
            accounts[A], accounts[B], creditline_given=clAB, creditline_received=clBA
        )
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

    path = [debtor, accounts[1], accounts[2], creditor]
    transfer_fees = 2

    network.functions.debitTransfer(
        debt_value, transfer_fees, path, EXTRA_DATA
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

    path = [debtor, accounts[1], accounts[2], creditor]
    transfer_fees = 2

    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        network.functions.debitTransfer(
            debt_value + 1, transfer_fees, path, EXTRA_DATA
        ).transact({"from": creditor})


def test_debit_transfer_under_value(
    currency_network_contract_with_trustlines_and_debt,
    accounts,
    creditor,
    debtor,
    debt_value,
):
    network = currency_network_contract_with_trustlines_and_debt

    path = [debtor, accounts[1], accounts[2], creditor]
    transfer_value = debt_value // 2
    transfer_fees = 2

    network.functions.debitTransfer(
        transfer_value, transfer_fees, path, EXTRA_DATA
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

    path = [debtor, accounts[1], accounts[1], creditor]
    transfer_value = debt_value // 2
    invalid_transfer_fees = 0

    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        network.functions.debitTransfer(
            transfer_value, invalid_transfer_fees, path, EXTRA_DATA
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

    path = [debtor, accounts[1], accounts[2], creditor]
    transfer_fees = 2

    network.functions.debitTransfer(
        debt_value, transfer_fees, path, EXTRA_DATA
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
        (max_int256, 0),
        (max_int256, -1),
        (max_int256, min_int256),
        (min_int256, 0),
        (min_int256, 1),
    ],
)
def test_safe_sum_no_error(currency_network_contract, a, b):
    assert currency_network_contract.functions.testSafeSumInt256(a, b).call() == a + b


@pytest.mark.parametrize(
    "a, b",
    [
        (max_int256, max_int256),
        (max_int256, 1),
        (min_int256, -1),
        (min_int256, min_int256),
    ],
)
def test_safe_sum_raises_error(currency_network_contract, a, b):
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        currency_network_contract.functions.testSafeSumInt256(a, b).call()


@pytest.mark.parametrize("creditor_index, debtor_index", [(1, 0), (0, 1)])
def test_add_to_debt_min_int256_fails(
    currency_network_contract, accounts, creditor_index, debtor_index
):
    """we should not be able to add to debt min_int256"""
    creditor = accounts[creditor_index]
    debtor = accounts[debtor_index]
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        currency_network_contract.functions.testAddToDebt(
            debtor, creditor, min_int256
        ).transact({"from": debtor})


@pytest.mark.parametrize("creditor_index, debtor_index", [(0, 1), (2, 3)])
def test_add_to_debt_max_int256_succeeds(
    currency_network_contract, accounts, creditor_index, debtor_index
):
    creditor = accounts[creditor_index]
    debtor = accounts[debtor_index]
    currency_network_contract.functions.testAddToDebt(
        debtor, creditor, max_int256
    ).transact({"from": debtor})
    assert (
        currency_network_contract.functions.getDebt(debtor, creditor).call()
        == max_int256
    )
    assert (
        currency_network_contract.functions.getDebt(creditor, debtor).call()
        == -max_int256
    )


@pytest.mark.parametrize("creditor_index, debtor_index", [(1, 0), (0, 1)])
def test_add_to_debt_twice_to_reach_min_int(
    currency_network_contract, accounts, creditor_index, debtor_index
):
    """We should not be able to overflow the debt by adding twice to it to reach min_int"""
    max_int = 2 ** 255 - 1
    creditor = accounts[creditor_index]
    debtor = accounts[debtor_index]
    currency_network_contract.functions.testAddToDebt(
        debtor, creditor, max_int
    ).transact({"from": debtor})
    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        currency_network_contract.functions.testAddToDebt(debtor, creditor, 2).transact(
            {"from": debtor}
        )
