#! pytest

import time
import pytest

import eth_tester.exceptions

from tldeploy.core import deploy_network
from tests.conftest import EXPIRATION_TIME, MAX_UINT_64, CurrencyNetworkAdapter

SECONDS_PER_YEAR = 60 * 60 * 24 * 365
NETWORK_SETTING = {
    "name": "TestCoin",
    "symbol": "T",
    "decimals": 6,
    "fee_divisor": 100,
    "default_interest_rate": 0,
    "custom_interests": True,
    "prevent_mediator_interests": False,
    "currency_network_contract_name": "TestCurrencyNetwork",
    "expiration_time": EXPIRATION_TIME,
}


@pytest.fixture(scope="session")
def currency_network_contract(web3):
    return deploy_network(web3, **NETWORK_SETTING)


@pytest.fixture(scope="session")
def currency_network_contract_no_fees(web3):
    network_setting = NETWORK_SETTING
    network_setting["fee_divisor"] = 0
    return deploy_network(web3, **NETWORK_SETTING)


@pytest.fixture(scope="session", params=[0, 100, 2000])  # 0% , 1%, 20%
def interest_rate(request):
    return request.param


@pytest.fixture()
def currency_network_contract_with_trustlines(chain, web3, accounts, interest_rate):
    currency_network_contract = deploy_network(web3, **NETWORK_SETTING)
    currency_network_adapter = CurrencyNetworkAdapter(currency_network_contract)
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

    currency_network_adapter.transfer(10000, path=[accounts[0], accounts[1]])
    chain.time_travel(current_time + SECONDS_PER_YEAR)

    return currency_network_contract


@pytest.fixture()
def currency_network_contract_with_max_uint_trustlines(
    currency_network_contract_no_fees, chain, web3, accounts
):
    """Currency network that uses max_unit64 for all credit limits"""
    currency_network_contract = currency_network_contract_no_fees
    currency_network_adapter = CurrencyNetworkAdapter(currency_network_contract)

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


def test_close_trustline(currency_network_contract, accounts):
    currency_network_adapter = CurrencyNetworkAdapter(currency_network_contract)
    A, B, *rest = accounts

    currency_network_adapter.update_trustline(
        A, B, creditline_given=1000, creditline_received=1000, accept=True
    )

    currency_network_adapter.close_trustline(A, B)
    assert currency_network_adapter.is_trustline_closed(A, B)


def test_cannot_close_with_balance(currency_network_contract, accounts):
    currency_network_adapter = CurrencyNetworkAdapter(currency_network_contract)
    A, B, *rest = accounts

    currency_network_adapter.update_trustline(
        A, B, creditline_given=1000, creditline_received=1000, accept=True
    )
    currency_network_adapter.transfer(20, path=[A, B])

    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        currency_network_adapter.close_trustline(A, B)


def test_cannot_reopen_closed_trustline(currency_network_contract, accounts):
    currency_network_adapter = CurrencyNetworkAdapter(currency_network_contract)
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
    currency_network_contract_with_trustlines, accounts
):
    currency_network_adapter = CurrencyNetworkAdapter(
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
    currency_network_contract_with_trustlines, accounts
):
    currency_network_adapter = CurrencyNetworkAdapter(
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
    currency_network_contract_with_max_uint_trustlines, accounts
):
    """Test that closing a trustline with a triangular transfer as big as max_uint64 succeed"""
    currency_network_adapter = CurrencyNetworkAdapter(
        currency_network_contract_with_max_uint_trustlines
    )
    max_uint64 = 2 ** 64 - 1
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
