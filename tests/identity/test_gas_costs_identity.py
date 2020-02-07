#! pytest
"""This file contains tests so that there is no regression in the gas costs,
 for example because of a different solidity version.
 The tests are meant to exhibit unexpected increase in gas costs.
 They are not meant to enforce a limit.
 """
import pytest
from tldeploy.core import deploy_identity

from tldeploy.identity import MetaTransaction, deploy_proxied_identity

from ..conftest import report_gas_costs, get_gas_costs


@pytest.fixture(scope="session")
def test_contract(deploy_contract):
    return deploy_contract("TestContract")


def test_deploy_identity(web3, accounts, table):
    A, *rest = accounts

    block_number_before = web3.eth.blockNumber

    deploy_identity(web3, A)

    block_number_after = web3.eth.blockNumber

    gas_cost = 0
    for block_number in range(block_number_after, block_number_before, -1):
        gas_cost += web3.eth.getBlock(block_number).gasUsed

    report_gas_costs(table, "Deploy Identity", gas_cost, limit=1_500_000)


def test_deploy_proxied_identity(
    web3,
    table,
    proxy_factory,
    identity_implementation,
    signature_of_owner_on_implementation,
):
    block_number_before = web3.eth.blockNumber

    deploy_proxied_identity(
        web3,
        proxy_factory.address,
        identity_implementation.address,
        signature_of_owner_on_implementation,
    )

    block_number_after = web3.eth.blockNumber

    gas_cost = 0
    for block_number in range(block_number_after, block_number_before, -1):
        gas_cost += web3.eth.getBlock(block_number).gasUsed

    report_gas_costs(table, "Deploy Proxied Identity", gas_cost, limit=310_000)


def test_meta_tx_over_regular_tx_overhead(
    web3, table, test_contract, identity, delegate
):
    """Tests the overhead of using a meta-tx compared to a regular tx"""
    # The test sends two meta-tx as the first meta-tx of an identity is more expensive than all the next ones
    # due to storage allocation

    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    # first meta-tx
    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    filled_meta_tx = identity.filled_and_signed_meta_transaction(meta_transaction)
    delegate.send_signed_meta_transaction(filled_meta_tx)

    # second meta-tx we meter
    second_filled_meta_transaction = identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    meta_tx_id = delegate.send_signed_meta_transaction(second_filled_meta_transaction)
    regular_tx_id = test_contract.functions.testFunction(argument).transact()

    gas_cost_meta_tx = get_gas_costs(web3, meta_tx_id)
    gas_cost_regular_tx = get_gas_costs(web3, regular_tx_id)

    overhead = gas_cost_meta_tx - gas_cost_regular_tx

    report_gas_costs(
        table, "Overhead of unproxied meta-tx over regular tx", overhead, limit=26_500
    )


def test_proxy_overhead(
    web3, table, test_contract, proxied_identity, identity, delegate
):
    """Tests the overhead of using an identity proxy compared to a regular identity"""

    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    proxied_meta_transaction = proxied_identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    not_proxied_meta_transaction = identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    proxied_meta_tx_id = delegate.send_signed_meta_transaction(proxied_meta_transaction)
    not_proxied_meta_tx_id = delegate.send_signed_meta_transaction(
        not_proxied_meta_transaction
    )

    gas_cost_proxied_meta_tx = get_gas_costs(web3, proxied_meta_tx_id)
    gas_cost_not_proxied_tx = get_gas_costs(web3, not_proxied_meta_tx_id)

    overhead = gas_cost_proxied_meta_tx - gas_cost_not_proxied_tx

    report_gas_costs(
        table, "Overhead of a proxy over non-proxy meta-tx", overhead, limit=1_500
    )


def test_meta_tx_over_own_identity_tx_overhead(
    web3, table, test_contract, identity, owner, delegate
):
    """Tests the overhead of using a meta-tx compared to an owned identity tx"""
    # The test sends two meta-tx as the first meta-tx of an identity is more expensive than all the next ones
    # due to storage allocation

    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    # first meta-tx
    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    filled_meta_tx = identity.filled_and_signed_meta_transaction(meta_transaction)
    delegate.send_signed_meta_transaction(filled_meta_tx)

    # second meta-tx we meter
    second_filled_meta_transaction = identity.filled_and_signed_meta_transaction(
        meta_transaction
    )
    meta_tx_id = delegate.send_signed_meta_transaction(second_filled_meta_transaction)
    owner_tx_id = identity.contract.functions.executeOwnerTransaction(
        to, 0, meta_transaction.data, 0, 0
    ).transact({"from": owner})

    gas_cost_meta_tx = get_gas_costs(web3, meta_tx_id)
    gas_cost_owner_tx = get_gas_costs(web3, owner_tx_id)

    overhead = gas_cost_meta_tx - gas_cost_owner_tx

    report_gas_costs(
        table,
        "Overhead of unproxied meta-tx over owned transaction",
        overhead,
        limit=22_000,
    )


def test_own_identity_meta_tx_overhead(
    web3, table, test_contract, identity, owner, delegate
):
    """Tests the overhead of using an owned meta-tx compared to a regular tx"""

    to = test_contract.address
    argument = 10
    function_call = test_contract.functions.testFunction(argument)

    meta_transaction = MetaTransaction.from_function_call(function_call, to=to)
    owner_tx_id = identity.contract.functions.executeOwnerTransaction(
        to, 0, meta_transaction.data, 0, 0
    ).transact({"from": owner})

    regular_tx_id = test_contract.functions.testFunction(argument).transact()

    gas_cost_owner_meta_tx = get_gas_costs(web3, owner_tx_id)
    gas_cost_regular_tx = get_gas_costs(web3, regular_tx_id)

    overhead = gas_cost_owner_meta_tx - gas_cost_regular_tx

    report_gas_costs(
        table,
        "Overhead of owned unproxied meta-tx over regular transaction",
        overhead,
        limit=5_000,
    )
