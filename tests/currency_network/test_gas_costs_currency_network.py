#! pytest
"""This file contains tests so that there is no regression in the gas costs,
 for example because of a different solidity version.
 The tests are meant to exhibit unexpected increase in gas costs.
 They are not meant to enforce a limit.

 The tests also show what gas limit could be used for certain transactions
 These values differ from the gas costs as some gas can be reimbursed at the end of a transaction
 e.g. for freeing storage.
 These values are to be used in the clientlib for gas limit of transactions.

 Every values are rounded up to the thousands
 """
import pytest
from tldeploy.core import deploy_network
from eth_utils.exceptions import ValidationError
import attr

from ..conftest import EXTRA_DATA, EXPIRATION_TIME, get_gas_costs, report_gas_costs

GAS_COST_TRANSFER_0_MEDIATOR = 61_000
GAS_COST_TRANSFER_1_MEDIATOR = 94_000
GAS_COST_TRANSFER_2_MEDIATORS = 128_000
GAS_COST_TRANSFER_3_MEDIATORS = 162_000
GAS_COST_FIRST_TL_REQUEST = 79_000
GAS_COST_SECOND_TL_REQUEST = 45_000
GAS_COST_FIRST_TL = 331_000
GAS_COST_UPDATE_TL = 40_000
GAS_COST_REDUCE_TL_LIMITS = 66_000
GAS_COST_CLOSE_TL_NO_TRANSFER = 55_000
GAS_COST_CLOSE_TL_TRIANGULAR_TRANSFER_2_MEDIATORS = 114_000
GAS_COST_CLOSE_TL_TRIANGULAR_TRANSFER_4_MEDIATORS = 181_000
GAS_COST_CANCEL_TL_UPDATE = 20_000

GAS_LIMIT_TRANSFER_0_MEDIATOR = GAS_COST_TRANSFER_0_MEDIATOR
GAS_LIMIT_TRANSFER_1_MEDIATOR = GAS_COST_TRANSFER_1_MEDIATOR
GAS_LIMIT_TRANSFER_2_MEDIATORS = GAS_COST_TRANSFER_2_MEDIATORS
GAS_LIMIT_TRANSFER_3_MEDIATORS = GAS_COST_TRANSFER_3_MEDIATORS
GAS_LIMIT_FIRST_TL_REQUEST = GAS_COST_FIRST_TL_REQUEST
GAS_LIMIT_SECOND_TL_REQUEST = GAS_COST_SECOND_TL_REQUEST
GAS_LIMIT_FIRST_TL = 341_000
GAS_LIMIT_UPDATE_TL = 59_000
GAS_LIMIT_REDUCE_TL_LIMITS = GAS_COST_REDUCE_TL_LIMITS
GAS_LIMIT_CLOSE_TL_NO_TRANSFER = 93_000
GAS_LIMIT_CLOSE_TL_TRIANGULAR_TRANSFER_2_MEDIATORS = 182_000
GAS_LIMIT_CLOSE_TL_TRIANGULAR_TRANSFER_4_MEDIATORS = 244_000
GAS_LIMIT_CANCEL_TL_UPDATE = 38_000


trustlines = [
    (0, 1, 100, 150),
    (1, 2, 200, 250),
    (2, 3, 300, 350),
    (3, 4, 400, 450),
    (0, 4, 500, 550),
    (1, 5, 100, 100),
    (5, 0, 100, 100),
]  # (A, B, clAB, clBA)


@attr.s
class GasValues:
    cost = attr.ib()
    limit = attr.ib()


@pytest.fixture(scope="session")
def currency_network_contract(web3):
    return deploy_network(
        web3,
        name="Teuro",
        symbol="TEUR",
        decimals=2,
        custom_interests=True,
        fee_divisor=100,
        currency_network_contract_name="TestCurrencyNetwork",
        expiration_time=EXPIRATION_TIME,
    )


@pytest.fixture(scope="session")
def currency_network_contract_with_trustlines(web3, accounts):
    contract = deploy_network(
        web3,
        name="Teuro",
        symbol="TEUR",
        decimals=2,
        fee_divisor=100,
        currency_network_contract_name="CurrencyNetwork",
        expiration_time=EXPIRATION_TIME,
    )
    for (A, B, clAB, clBA) in trustlines:
        contract.functions.updateTrustline(
            accounts[B], clAB, clBA, 0, 0, False
        ).transact({"from": accounts[A]})
        contract.functions.updateTrustline(
            accounts[A], clBA, clAB, 0, 0, False
        ).transact({"from": accounts[B]})
    return contract


def find_gas_values_for_call(web3, contract_call, transaction_options=None):
    if transaction_options is None:
        transaction_options = {}

    gas_limit = 20_000
    tx_success = False

    while not tx_success:
        gas_limit += 1_000
        transaction_options["gas"] = gas_limit
        try:
            tx_hash = contract_call.transact(transaction_options)
            tx_success = web3.eth.waitForTransactionReceipt(tx_hash, 5).status == 1
        except ValidationError as e:
            if "Insufficient gas" not in e.args:
                raise e
            tx_success = False

    gas_cost = get_gas_costs(web3, tx_hash)
    return GasValues(limit=gas_limit, cost=gas_cost)


def assert_transaction_successful(web3, tx_hash):
    tx_receipt = web3.eth.waitForTransactionReceipt(tx_hash, 5)
    assert tx_receipt.status == 1, "Transaction failed, check gas limit"


def test_cost_transfer_0_mediators(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    # Verify that we test the most gas expensive case where we change the balance from 0 to non-zero
    assert contract.functions.balance(A, B).call() == 0
    tx_hash = contract.functions.transfer(100, 2, [A, B], EXTRA_DATA).transact(
        {"from": A, "gas": GAS_LIMIT_TRANSFER_0_MEDIATOR}
    )
    assert_transaction_successful(web3, tx_hash)
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(
        table, "0 hop transfer", gas_cost, limit=GAS_COST_TRANSFER_0_MEDIATOR
    )


def test_cost_transfer_1_mediators(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, C, *rest = accounts
    tx_hash = contract.functions.transfer(50, 4, [A, B, C], EXTRA_DATA).transact(
        {"from": A, "gas": GAS_LIMIT_TRANSFER_1_MEDIATOR}
    )
    assert_transaction_successful(web3, tx_hash)
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(
        table, "1 hop transfer", gas_cost, limit=GAS_COST_TRANSFER_1_MEDIATOR
    )


def test_cost_transfer_2_mediators(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, C, D, *rest = accounts
    tx_hash = contract.functions.transfer(50, 6, [A, B, C, D], EXTRA_DATA).transact(
        {"from": A, "gas": GAS_LIMIT_TRANSFER_2_MEDIATORS}
    )
    assert_transaction_successful(web3, tx_hash)
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(
        table, "2 hop transfer", gas_cost, limit=GAS_COST_TRANSFER_2_MEDIATORS
    )


def test_cost_transfer_3_mediators(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, C, D, E, *rest = accounts
    tx_hash = contract.functions.transfer(50, 8, [A, B, C, D, E], EXTRA_DATA).transact(
        {"from": A, "gas": GAS_LIMIT_TRANSFER_3_MEDIATORS}
    )
    assert_transaction_successful(web3, tx_hash)
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(
        table, "3 hop transfer", gas_cost, limit=GAS_COST_TRANSFER_3_MEDIATORS
    )


def test_cost_first_trustline_request(web3, currency_network_contract, accounts, table):
    contract = currency_network_contract
    A, B, *rest = accounts
    tx_hash = contract.functions.updateTrustline(
        B, 150, 150, 1000, 1000, False
    ).transact({"from": A, "gas": GAS_LIMIT_FIRST_TL_REQUEST})
    assert_transaction_successful(web3, tx_hash)
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(
        table,
        "First Trustline Update Request",
        gas_cost,
        limit=GAS_COST_FIRST_TL_REQUEST,
    )


def test_cost_second_trustline_request(
    web3, currency_network_contract, accounts, table
):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.functions.updateTrustline(B, 149, 149, 1000, 1000, False).transact(
        {"from": A}
    )
    tx_hash = contract.functions.updateTrustline(
        B, 150, 150, 2000, 2000, False
    ).transact({"from": A, "gas": GAS_LIMIT_SECOND_TL_REQUEST})
    assert_transaction_successful(web3, tx_hash)
    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(
        table,
        "Second Trustline Update Request",
        gas_cost,
        limit=GAS_COST_SECOND_TL_REQUEST,
    )


def test_cost_first_trustline(web3, currency_network_contract, accounts, table):
    contract = currency_network_contract
    A, B, *rest = accounts
    assert contract.functions.creditline(A, B).call() == 0

    contract.functions.updateTrustline(B, 150, 150, 1000, 1000, False).transact(
        {"from": A}
    )
    call = contract.functions.updateTrustline(A, 150, 150, 1000, 1000, False)
    gas_values = find_gas_values_for_call(web3, call, {"from": B})
    assert gas_values.limit == GAS_LIMIT_FIRST_TL

    report_gas_costs(table, "First Trustline", gas_values.cost, limit=GAS_COST_FIRST_TL)


def test_cost_update_trustline(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.functions.creditline(A, B).call() == 100

    contract.functions.updateTrustline(B, 150, 150, 1000, 1000, False).transact(
        {"from": A}
    )
    call = contract.functions.updateTrustline(A, 150, 150, 1000, 1000, False)
    gas_values = find_gas_values_for_call(web3, call, {"from": B})
    assert gas_values.limit == GAS_LIMIT_UPDATE_TL

    report_gas_costs(
        table, "Update Trustline", gas_values.cost, limit=GAS_COST_UPDATE_TL
    )


def test_cost_update_reduce_need_no_accept_trustline(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.functions.creditline(A, B).call() == 100
    tx_hash = contract.functions.updateCreditlimits(B, 99, 150).transact(
        {"from": A, "gas": GAS_LIMIT_REDUCE_TL_LIMITS}
    )
    assert contract.functions.creditline(A, B).call() == 99
    assert_transaction_successful(web3, tx_hash)

    gas_cost = get_gas_costs(web3, tx_hash)
    report_gas_costs(
        table, "Reduce Trustline", gas_cost, limit=GAS_COST_REDUCE_TL_LIMITS
    )


def test_cost_close_trustline_no_transfer(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, C, *rest = accounts
    assert contract.functions.balance(B, C).call() == 0

    call = contract.functions.closeTrustline(B)
    gas_values = find_gas_values_for_call(web3, call, {"from": C})
    assert gas_values.limit == GAS_LIMIT_CLOSE_TL_NO_TRANSFER

    report_gas_costs(
        table,
        "Close Trustline no transfer",
        gas_values.cost,
        limit=GAS_COST_CLOSE_TL_NO_TRANSFER,
    )


def test_cost_close_trustline_triangular_transfer_2_mediators(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    C = accounts[5]
    contract.functions.transfer(1, 1, [B, A], EXTRA_DATA).transact({"from": B})
    assert contract.functions.balance(A, B).call() > 0

    call = contract.functions.closeTrustlineByTriangularTransfer(B, 10, [A, B, C, A])
    gas_values = find_gas_values_for_call(web3, call, {"from": A})
    assert gas_values.limit == GAS_LIMIT_CLOSE_TL_TRIANGULAR_TRANSFER_2_MEDIATORS

    report_gas_costs(
        table,
        "Close Trustline triangular 2 hops",
        gas_values.cost,
        limit=GAS_COST_CLOSE_TL_TRIANGULAR_TRANSFER_2_MEDIATORS,
    )


def test_cost_close_trustline_triangular_transfer_4_mediators(
    web3, currency_network_contract_with_trustlines, accounts, table
):
    contract = currency_network_contract_with_trustlines
    A, B, C, D, E, *rest = accounts
    contract.functions.transfer(1, 1, [B, A], EXTRA_DATA).transact({"from": B})
    assert contract.functions.balance(A, B).call() > 0

    call = contract.functions.closeTrustlineByTriangularTransfer(
        B, 10, [A, B, C, D, E, A]
    )

    gas_values = find_gas_values_for_call(web3, call, {"from": A})
    assert gas_values.limit == GAS_LIMIT_CLOSE_TL_TRIANGULAR_TRANSFER_4_MEDIATORS

    report_gas_costs(
        table,
        "Close Trustline triangular 4 hops",
        gas_values.cost,
        limit=GAS_COST_CLOSE_TL_TRIANGULAR_TRANSFER_4_MEDIATORS,
    )


def test_cancel_trustline_update(web3, currency_network_contract, accounts, table):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.functions.updateCreditlimits(B, 150, 150).transact({"from": A})
    call = contract.functions.cancelTrustlineUpdate(B)
    gas_values = find_gas_values_for_call(web3, call, {"from": A})
    assert gas_values.limit == GAS_LIMIT_CANCEL_TL_UPDATE

    report_gas_costs(
        table,
        "Cancel trustline update",
        gas_values.cost,
        limit=GAS_COST_CANCEL_TL_UPDATE,
    )
