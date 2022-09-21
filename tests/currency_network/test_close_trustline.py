#! pytest

import time
import pytest
from tldeploy.core import NetworkSettings

from tests.conftest import (
    MAX_UINT_64,
    CurrencyNetworkAdapter,
    get_single_event_of_contract,
)
from tests.currency_network.conftest import deploy_test_network

SECONDS_PER_YEAR = 60 * 60 * 24 * 365
NETWORK_SETTING = NetworkSettings(fee_divisor=100, custom_interests=True)


@pytest.fixture(scope="session", params=[0, 100, 2000])  # 0% , 1%, 20%
def interest_rate(request):
    return request.param


@pytest.fixture()
def currency_network_contract_with_trustlines(
    chain, web3, accounts, interest_rate, make_currency_network_adapter
):
    currency_network_contract = deploy_test_network(web3, NETWORK_SETTING)
    currency_network_adapter = make_currency_network_adapter(currency_network_contract)
    current_time = int(time.time())
    chain.time_travel(current_time + 10)

    for a in accounts[:4]:
        for b in accounts[:4]:
            if a is b:
                continue
            currency_network_adapter.set_account(
                a,
                b,
                creditline_given=1_000_000,
                creditline_received=1_000_000,
                interest_rate_given=interest_rate,
                interest_rate_received=interest_rate,
                m_time=current_time,
            )

    currency_network_adapter.transfer(10_000, path=[accounts[0], accounts[1]])
    chain.time_travel(current_time + SECONDS_PER_YEAR)

    return currency_network_contract


@pytest.fixture()
def currency_network_adapter_with_trustlines(
    currency_network_contract_with_trustlines, make_currency_network_adapter
):
    return make_currency_network_adapter(currency_network_contract_with_trustlines)


@pytest.fixture()
def currency_network_contract_with_max_uint_trustlines(
    currency_network_contract_custom_interest,
    chain,
    web3,
    accounts,
    make_currency_network_adapter,
):
    """Currency network that uses max_unit64 for all credit limits"""
    currency_network_contract = currency_network_contract_custom_interest
    currency_network_adapter = make_currency_network_adapter(currency_network_contract)

    for a in accounts[:3]:
        for b in accounts[:3]:
            if a is b:
                continue
            currency_network_adapter.set_account(
                a,
                b,
                creditline_given=MAX_UINT_64,
                creditline_received=MAX_UINT_64,
                interest_rate_given=1,
                interest_rate_received=1,
            )

    return currency_network_contract


def test_close_trustline(currency_network_adapter_with_fees, accounts):
    currency_network_adapter = currency_network_adapter_with_fees
    A, B, *rest = accounts

    currency_network_adapter.update_trustline(
        A, B, creditline_given=1000, creditline_received=1000, accept=True
    )

    currency_network_adapter.close_trustline(A, B)
    assert currency_network_adapter.is_trustline_closed(A, B)


def test_cannot_close_with_balance(
    currency_network_adapter_with_fees, accounts, assert_failing_transaction
):
    currency_network_adapter = currency_network_adapter_with_fees
    A, B, *rest = accounts

    currency_network_adapter.update_trustline(
        A, B, creditline_given=1000, creditline_received=1000, accept=True
    )
    currency_network_adapter.transfer(20, path=[A, B])

    assert_failing_transaction(
        currency_network_adapter.contract.functions.closeTrustline(B), {"from": A}
    )


def test_cannot_reopen_closed_trustline(currency_network_adapter_with_fees, accounts):
    currency_network_adapter = currency_network_adapter_with_fees
    A, B, *rest = accounts

    currency_network_adapter.update_trustline(
        A, B, creditline_given=1000, creditline_received=1000
    )
    currency_network_adapter.close_trustline(A, B)
    currency_network_adapter.update_trustline(
        B, A, creditline_given=1000, creditline_received=1000
    )
    assert currency_network_adapter.is_trustline_closed(A, B)


def test_close_trustline_negative_balance(
    currency_network_contract_with_trustlines, accounts, make_currency_network_adapter
):
    currency_network_adapter = make_currency_network_adapter(
        currency_network_contract_with_trustlines
    )
    A, B, C, D, E, *rest = accounts

    def get_balance():
        return currency_network_adapter.balance(A, B)

    assert get_balance() < 0

    currency_network_adapter.close_trustline(A, B, path=[A, C, D, B, A])

    assert get_balance() == 0
    assert currency_network_adapter.is_trustline_closed(A, B)


def test_close_trustline_positive_balance(
    currency_network_contract_with_trustlines, accounts, make_currency_network_adapter
):
    currency_network_adapter = make_currency_network_adapter(
        currency_network_contract_with_trustlines
    )
    A, B, C, D, E, *rest = accounts

    def get_balance():
        return currency_network_adapter.balance(B, A)

    assert get_balance() > 0

    currency_network_adapter.close_trustline(B, A, path=[B, A, C, D, B])

    assert get_balance() == 0
    assert currency_network_adapter.is_trustline_closed(A, B)


def test_close_trustline_max_balance(
    currency_network_contract_with_max_uint_trustlines,
    accounts,
    make_currency_network_adapter,
):
    """Test that closing a trustline with a triangular transfer as big as max_uint64 succeed"""
    currency_network_adapter = make_currency_network_adapter(
        currency_network_contract_with_max_uint_trustlines
    )
    max_uint64 = 2**64 - 1
    A, B, C, *rest = accounts

    currency_network_adapter.set_account(
        A,
        B,
        creditline_given=max_uint64,
        creditline_received=max_uint64,
        interest_rate_given=1,
        interest_rate_received=1,
        balance=max_uint64,
    )

    def get_balance():
        return currency_network_adapter.balance(A, B)

    assert get_balance() == max_uint64

    currency_network_adapter.close_trustline(A, B, path=[A, B, C, A])

    assert get_balance() == 0


def test_close_trustline_direct_transfer_no_balance(
    currency_network_adapter_with_trustlines: CurrencyNetworkAdapter, accounts
):
    from_address = accounts[1]
    to_address = accounts[2]
    assert (
        currency_network_adapter_with_trustlines.balance(from_address, to_address) == 0
    )
    currency_network_adapter_with_trustlines.close_trustline_by_direct_transfer(
        from_address, to_address
    )

    assert currency_network_adapter_with_trustlines.is_trustline_closed(
        from_address, to_address
    )


def test_close_trustline_direct_transfer_with_balance(
    currency_network_adapter_with_trustlines: CurrencyNetworkAdapter, accounts
):
    from_address = accounts[1]
    to_address = accounts[0]
    assert (
        currency_network_adapter_with_trustlines.balance(from_address, to_address)
        == 10_000
    )
    currency_network_adapter_with_trustlines.close_trustline_by_direct_transfer(
        from_address, to_address, min_balance=10_000, max_balance=20_000
    )

    assert currency_network_adapter_with_trustlines.is_trustline_closed(
        from_address, to_address
    )


def test_close_trustline_direct_transfer_event(
    currency_network_adapter_with_trustlines: CurrencyNetworkAdapter, accounts, web3
):
    from_address = accounts[1]
    to_address = accounts[0]

    (
        creditline_given,
        creditline_received,
        interest_rate_given,
        interest_rate_received,
        is_frozen,
        m_time,
        balance,
    ) = currency_network_adapter_with_trustlines.get_account(from_address, to_address)

    currency_network_adapter_with_trustlines.close_trustline_by_direct_transfer(
        from_address, to_address, min_balance=10_000, max_balance=20_000
    )

    block_time = web3.eth.getBlock("latest")["timestamp"]
    last_block_number = web3.eth.blockNumber
    balance_with_interests = (
        currency_network_adapter_with_trustlines.balance_with_interests(
            balance, m_time, block_time, interest_rate_given, interest_rate_received
        )
    )

    assert currency_network_adapter_with_trustlines.is_trustline_closed(
        from_address, to_address
    )

    transfer_event_args = get_single_event_of_contract(
        currency_network_adapter_with_trustlines.contract, "Transfer", last_block_number
    )["args"]
    assert transfer_event_args["_from"] == from_address
    assert transfer_event_args["_to"] == to_address
    assert transfer_event_args["_value"] == balance_with_interests
    assert transfer_event_args["_extraData"] == b""

    balance_update_event_args = get_single_event_of_contract(
        currency_network_adapter_with_trustlines.contract,
        "BalanceUpdate",
        last_block_number,
    )["args"]
    assert balance_update_event_args["_from"] == from_address
    assert balance_update_event_args["_to"] == to_address
    assert balance_update_event_args["_value"] == 0

    trustline_update_event_args = get_single_event_of_contract(
        currency_network_adapter_with_trustlines.contract,
        "TrustlineUpdate",
        last_block_number,
    )["args"]
    assert trustline_update_event_args["_creditor"] == from_address
    assert trustline_update_event_args["_debtor"] == to_address
    assert trustline_update_event_args["_creditlineGiven"] == 0
    assert trustline_update_event_args["_creditlineReceived"] == 0
    assert trustline_update_event_args["_interestRateGiven"] == 0
    assert trustline_update_event_args["_interestRateReceived"] == 0
    assert trustline_update_event_args["_isFrozen"] is False


def test_close_trustline_max_balance_fails(
    currency_network_adapter_custom_interest: CurrencyNetworkAdapter, accounts
):
    """Test that trying to close a trustline with max balance fails when the balance exceeds max balance"""
    from_address = accounts[0]
    to_address = accounts[1]

    balance = 100

    currency_network_adapter_custom_interest.set_account(
        from_address,
        to_address,
        creditline_given=1_000,
        creditline_received=1_000,
        balance=balance,
    )

    currency_network_adapter_custom_interest.close_trustline_by_direct_transfer(
        from_address, to_address, max_balance=balance - 1, should_fail=True
    )


def test_close_trustline_min_balance_fails(
    currency_network_adapter_custom_interest: CurrencyNetworkAdapter, accounts
):
    """Test that trying to close a trustline with min balance fails when the balance is below min balance"""
    from_address = accounts[0]
    to_address = accounts[1]

    balance = 100

    currency_network_adapter_custom_interest.set_account(
        from_address,
        to_address,
        creditline_given=1_000,
        creditline_received=1_000,
        balance=balance,
    )

    currency_network_adapter_custom_interest.close_trustline_by_direct_transfer(
        from_address,
        to_address,
        min_balance=balance + 1,
        max_balance=2 * balance,
        should_fail=True,
    )


def test_close_trustline_interest_overflows(
    currency_network_adapter_custom_interest: CurrencyNetworkAdapter, accounts, web3
):
    """Test that if the interests would put the balance above `max_balance`
    then the call to close the trustline with direct transfer fails"""
    from_address = accounts[0]
    to_address = accounts[1]

    current_time = web3.eth.getBlock("latest")["timestamp"]
    one_year_ago = current_time - SECONDS_PER_YEAR
    balance = 100

    currency_network_adapter_custom_interest.set_account(
        from_address,
        to_address,
        creditline_given=1_000,
        creditline_received=1_000,
        interest_rate_given=100,
        interest_rate_received=100,
        m_time=one_year_ago,
        balance=balance,
    )

    currency_network_adapter_custom_interest.close_trustline_by_direct_transfer(
        from_address, to_address, max_balance=balance, should_fail=True
    )
