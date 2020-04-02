#! pytest
"""This file contains tests so that there is no regression in the gas costs,
 for example because of a different solidity version.
 The tests are meant to exhibit unexpected increase in gas costs.
 They are not meant to enforce a limit.

 The tests also show what gas limit could be used for certain transactions
 These values differ from the gas costs as some gas can be reimbursed at the end of a transaction
 e.g. for freeing storage.
 These values are to be used in the clientlib for gas limit of transactions.

 The gas costs for the tests are automatically stored in the file 'gas_values.csv'
 If the gas cost changes and you need to change these values, run the tests with '--update-gas-values'

The gas limit values are rounded up to the thousands
 """
import pytest
from tldeploy.core import deploy_network

from ..conftest import EXTRA_DATA, EXPIRATION_TIME


trustlines = [
    (0, 1, 100, 150),
    (1, 2, 200, 250),
    (2, 3, 300, 350),
    (3, 4, 400, 450),
    (0, 4, 500, 550),
    (1, 5, 100, 100),
    (5, 0, 100, 100),
]  # (A, B, clAB, clBA)


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


def test_cost_transfer_0_mediators(
    web3, currency_network_contract_with_trustlines, accounts, gas_values_snapshot
):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    # Verify that we test the most gas expensive case where we change the balance from 0 to non-zero
    assert contract.functions.balance(A, B).call() == 0
    gas_values_snapshot.assert_gas_values_for_call(
        "TRANSFER_0_MEDIATOR",
        web3,
        contract.functions.transfer(100, 2, [A, B], EXTRA_DATA),
        transaction_options={"from": A},
    )


def test_cost_transfer_1_mediators(
    web3, currency_network_contract_with_trustlines, accounts, gas_values_snapshot
):
    contract = currency_network_contract_with_trustlines
    A, B, C, *rest = accounts
    gas_values_snapshot.assert_gas_values_for_call(
        "TRANSFER_1_MEDIATOR",
        web3,
        contract.functions.transfer(50, 4, [A, B, C], EXTRA_DATA),
        transaction_options={"from": A},
    )


def test_cost_transfer_2_mediators(
    web3, currency_network_contract_with_trustlines, accounts, gas_values_snapshot
):
    contract = currency_network_contract_with_trustlines
    A, B, C, D, *rest = accounts
    gas_values_snapshot.assert_gas_values_for_call(
        "TRANSFER_2_MEDIATORS",
        web3,
        contract.functions.transfer(50, 6, [A, B, C, D], EXTRA_DATA),
        transaction_options={"from": A},
    )


def test_cost_transfer_3_mediators(
    web3, currency_network_contract_with_trustlines, accounts, gas_values_snapshot
):
    contract = currency_network_contract_with_trustlines
    A, B, C, D, E, *rest = accounts
    gas_values_snapshot.assert_gas_values_for_call(
        "TRANSFER_3_MEDIATORS",
        web3,
        contract.functions.transfer(50, 8, [A, B, C, D, E], EXTRA_DATA),
        transaction_options={"from": A},
    )


def test_cost_first_trustline_request(
    web3, currency_network_contract, accounts, gas_values_snapshot
):
    contract = currency_network_contract
    A, B, *rest = accounts
    gas_values_snapshot.assert_gas_values_for_call(
        "FIRST_TL_REQUEST",
        web3,
        contract.functions.updateTrustline(B, 150, 150, 1000, 1000, False),
        transaction_options={"from": A},
    )


def test_cost_second_trustline_request(
    web3, currency_network_contract, accounts, gas_values_snapshot
):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.functions.updateTrustline(B, 149, 149, 1000, 1000, False).transact(
        {"from": A}
    )
    gas_values_snapshot.assert_gas_values_for_call(
        "SECOND_TL_REQUEST",
        web3,
        contract.functions.updateTrustline(B, 150, 150, 2000, 2000, False),
        transaction_options={"from": A},
    )


def test_cost_first_trustline(
    web3, currency_network_contract, accounts, gas_values_snapshot
):
    contract = currency_network_contract
    A, B, *rest = accounts
    assert contract.functions.creditline(A, B).call() == 0
    contract.functions.updateTrustline(B, 150, 150, 1000, 1000, False).transact(
        {"from": A}
    )

    gas_values_snapshot.assert_gas_values_for_call(
        "FIRST_TL",
        web3,
        contract.functions.updateTrustline(A, 150, 150, 1000, 1000, False),
        transaction_options={"from": B},
    )


def test_cost_update_trustline(
    web3, currency_network_contract_with_trustlines, accounts, gas_values_snapshot
):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.functions.creditline(A, B).call() == 100
    contract.functions.updateTrustline(B, 150, 150, 1000, 1000, False).transact(
        {"from": A}
    )

    gas_values_snapshot.assert_gas_values_for_call(
        "UPDATE_TL",
        web3,
        contract.functions.updateTrustline(A, 150, 150, 1000, 1000, False),
        transaction_options={"from": B},
    )


def test_cost_update_reduce_need_no_accept_trustline(
    web3, currency_network_contract_with_trustlines, accounts, gas_values_snapshot
):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    assert contract.functions.creditline(A, B).call() == 100

    gas_values_snapshot.assert_gas_values_for_call(
        "REDUCE_TL_LIMITS",
        web3,
        contract.functions.updateCreditlimits(B, 99, 150),
        transaction_options={"from": A},
    )


def test_cost_close_trustline_no_transfer(
    web3, currency_network_contract_with_trustlines, accounts, gas_values_snapshot
):
    contract = currency_network_contract_with_trustlines
    A, B, C, *rest = accounts
    assert contract.functions.balance(B, C).call() == 0

    gas_values_snapshot.assert_gas_values_for_call(
        "CLOSE_TL_NO_TRANSFER",
        web3,
        contract.functions.closeTrustline(B),
        transaction_options={"from": C},
    )


def test_cost_close_trustline_triangular_transfer_2_mediators(
    web3, currency_network_contract_with_trustlines, accounts, gas_values_snapshot
):
    contract = currency_network_contract_with_trustlines
    A, B, *rest = accounts
    C = accounts[5]
    contract.functions.transfer(1, 1, [B, A], EXTRA_DATA).transact({"from": B})
    assert contract.functions.balance(A, B).call() > 0

    call = contract.functions.closeTrustlineByTriangularTransfer(B, 10, [A, B, C, A])

    gas_values_snapshot.assert_gas_values_for_call(
        "CLOSE_TL_TRIANGULAR_TRANSFER_2_MEDIATORS",
        web3,
        call,
        transaction_options={"from": A},
    )


def test_cost_close_trustline_triangular_transfer_4_mediators(
    web3, currency_network_contract_with_trustlines, accounts, gas_values_snapshot
):
    contract = currency_network_contract_with_trustlines
    A, B, C, D, E, *rest = accounts
    contract.functions.transfer(1, 1, [B, A], EXTRA_DATA).transact({"from": B})
    assert contract.functions.balance(A, B).call() > 0

    call = contract.functions.closeTrustlineByTriangularTransfer(
        B, 10, [A, B, C, D, E, A]
    )

    gas_values_snapshot.assert_gas_values_for_call(
        "CLOSE_TL_TRIANGULAR_TRANSFER_4_MEDIATORS",
        web3,
        call,
        transaction_options={"from": A},
    )


def test_cancel_trustline_update(
    web3, currency_network_contract, accounts, gas_values_snapshot
):
    contract = currency_network_contract
    A, B, *rest = accounts
    contract.functions.updateCreditlimits(B, 150, 150).transact({"from": A})
    call = contract.functions.cancelTrustlineUpdate(B)

    gas_values_snapshot.assert_gas_values_for_call(
        "CANCEL_TL_UPDATE", web3, call, transaction_options={"from": A}
    )
